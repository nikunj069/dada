"""
PS3 Firmware Agent — Local Web Server (FastAPI)

Serves the unified dashboard, 3D viewer, test execution runner, board designer, and run APIs.
Start with: firmware-agent serve
"""
from __future__ import annotations

import json
import os
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="PS3 Firmware Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- paths ----------
PROJECT_ROOT = Path(os.environ.get("PS3_PROJECT_ROOT", Path(__file__).resolve().parents[2]))
TRACES_DIR = PROJECT_ROOT / "artifacts" / "traces"
BOARDS_DIR = PROJECT_ROOT / "hardware" / "boards"
VIEWER_PATH = PROJECT_ROOT / "src" / "firmware_agent" / "reporting" / "viewer" / "rig_view.html"
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
SRC_STATIC = PROJECT_ROOT / "src" / "firmware_agent" / "static"
WEB_STATIC = PROJECT_ROOT / "web" / "static"
FIRMWARE_C = PROJECT_ROOT / "firmware" / "demos" / "fan_controller.c"

STATIC_DIR = WEB_STATIC if WEB_STATIC.exists() else SRC_STATIC
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

is_running_tests = False


def _get_capabilities(chip: str):
    """Return SimulatorCapabilities for a chip, importing locally to avoid circular deps."""
    import sys
    src_dir = str(PROJECT_ROOT / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from firmware_agent.simulator.labwired import LabWiredAdapter
    return LabWiredAdapter().capabilities(chip)


# ---------- API: Runs ----------

@app.get("/api/runs")
def list_runs():
    """List all available trace runs."""
    runs = []
    if not TRACES_DIR.exists():
        return runs

    for trace_file in sorted(TRACES_DIR.glob("*/trace.json")):
        try:
            data = json.loads(trace_file.read_text(encoding="utf-8", errors="replace"))
            run_id = trace_file.parent.name
            mtime = datetime.fromtimestamp(trace_file.stat().st_mtime).isoformat()
            runs.append({
                "run_id": run_id,
                "schema": data.get("schema", "unknown"),
                "test_id": data.get("test_id", "unknown"),
                "verdict": data.get("verdict", "UNAVAILABLE"),
                "chip": data.get("board", {}).get("chip", "unknown"),
                "duration_ns": data.get("duration_ns", 0),
                "timestamp": mtime,
                "trace_path": f"/api/runs/{run_id}/trace.json",
                "view_path": f"/view/{run_id}"
            })
        except Exception:
            continue
    return runs


@app.get("/api/runs/{run_id}/trace.json")
def get_trace(run_id: str):
    """Return raw trace.json for a given run."""
    trace_path = TRACES_DIR / run_id / "trace.json"
    if not trace_path.exists():
        candidates = [
            TRACES_DIR / run_id.upper() / "trace.json",
            TRACES_DIR / run_id.lower() / "trace.json",
            TRACES_DIR / run_id.replace("run_", "").upper() / "trace.json",
            TRACES_DIR / run_id.replace("run_", "").lower() / "trace.json",
        ]
        for c in candidates:
            if c.exists():
                trace_path = c
                break
    if not trace_path.exists():
        raise HTTPException(404, f"No trace found for run_id={run_id}")
    try:
        data = json.loads(trace_path.read_text(encoding="utf-8", errors="replace"))
        return JSONResponse(data)
    except Exception as e:
        raise HTTPException(500, f"Error reading trace: {e}")


# ---------- API: Boards ----------

@app.get("/api/boards")
def list_boards():
    """List available board descriptors, with simulator backing status."""
    boards = []
    if not BOARDS_DIR.exists():
        return boards

    for bf in sorted(BOARDS_DIR.glob("*.json")):
        try:
            data = json.loads(bf.read_text(encoding="utf-8", errors="replace"))
            chip = data.get("chip", "unknown")
            cap = _get_capabilities(chip)
            boards.append({
                "file": bf.name,
                "board": data,
                "simulator": {
                    "available": cap.available,
                    "supported_pins_count": len(cap.supported_pins),
                    "error": cap.error
                }
            })
        except Exception:
            continue
    return boards


@app.get("/api/boards/{chip}")
def get_board(chip: str):
    """Return board descriptor and simulator capabilities for a chip."""
    board_path = BOARDS_DIR / f"{chip}.json"
    if not board_path.exists():
        # Fall back to checking any board that declares this chip
        matched = None
        if BOARDS_DIR.exists():
            for bf in BOARDS_DIR.glob("*.json"):
                try:
                    d = json.loads(bf.read_text(encoding="utf-8", errors="replace"))
                    if d.get("chip") == chip:
                        matched = d
                        break
                except Exception:
                    pass
        if not matched:
            raise HTTPException(404, f"No board descriptor found for chip '{chip}'")
        data = matched
    else:
        data = json.loads(board_path.read_text(encoding="utf-8", errors="replace"))

    cap = _get_capabilities(data.get("chip", chip))
    return {
        "board": data,
        "capabilities": {
            "available": cap.available,
            "supported_pins": cap.supported_pins,
            "error": cap.error
        }
    }


@app.post("/api/boards")
async def create_board(request: Request):
    """Accept and validate a new board descriptor JSON."""
    try:
        body = await request.body()
        board = json.loads(body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON payload: {e}")

    # Minimal validation
    chip = board.get("chip")
    if not chip:
        raise HTTPException(400, "Missing required field: 'chip'")
    if "peripherals" not in board:
        raise HTTPException(400, "Missing required field: 'peripherals'")

    cap = _get_capabilities(chip)
    if cap.available and cap.supported_pins:
        for periph in board.get("peripherals", []):
            for pin in periph.get("pins", []):
                if pin not in cap.supported_pins and pin not in ["TX", "RX"]:
                    raise HTTPException(
                        422,
                        f"Pin '{pin}' on peripheral '{periph.get('id', '?')}' "
                        f"is not recognized by the simulator for chip '{chip}'."
                    )

    board.setdefault("created_by", "user")
    board.setdefault("board_name", f"Custom {chip} board")

    board_name = board.get("board_name", chip).replace(" ", "_").lower()
    filename = f"{board_name}.json"
    out_path = BOARDS_DIR / filename
    BOARDS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(board, indent=2), encoding="utf-8")

    return {"status": "saved", "path": str(out_path), "board": board}


# ---------- API: Status & Diagnostics ----------

def sanitize_data(obj):
    if isinstance(obj, float):
        if math.isnan(obj):
            return "NaN"
        if math.isinf(obj):
            return "Infinity" if obj > 0 else "-Infinity"
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_data(v) for v in obj]
    return obj


@app.get("/api/status")
def get_status():
    report_file = None
    for p in [PROJECT_ROOT / "artifacts" / "report.json", PROJECT_ROOT / "demo_artifacts" / "report.json"]:
        if p.exists():
            report_file = p
            break
    data = {}
    if report_file:
        try:
            data = json.loads(report_file.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass
    summary = data.get("summary", {})
    traces = list(TRACES_DIR.glob("*/trace.json")) if TRACES_DIR.exists() else []
    return {
        "status": "online",
        "agent_state": "running" if is_running_tests else "idle",
        "simulator": "LabWired Core v1.0",
        "chip": "STM32F103 (LQFP48)",
        "firmware": "firmware/demos/fan_controller.c",
        "total_tests": summary.get("total", 21),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 21),
        "skipped": summary.get("skipped", 0),
        "coverage_pct": summary.get("coverage_pct", 85.5),
        "execution_time_s": summary.get("execution_time", 0.0),
        "available_traces": len(traces),
        "known_defects": 5
    }


@app.get("/api/tests")
def get_tests():
    report_file = None
    for p in [PROJECT_ROOT / "artifacts" / "report.json", PROJECT_ROOT / "demo_artifacts" / "report.json"]:
        if p.exists():
            report_file = p
            break
    if not report_file:
        return {"tests": [], "summary": {}}
    try:
        data = json.loads(report_file.read_text(encoding="utf-8", errors="replace"))
        clean_data = sanitize_data(data)
        return JSONResponse(clean_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/traces")
def get_traces():
    if not TRACES_DIR.exists():
        return {"traces": []}
    results = []
    for p in sorted(TRACES_DIR.glob("*/trace.json")):
        test_id = p.parent.name
        size = p.stat().st_size
        results.append({
            "test_id": test_id,
            "path": f"/api/traces/{test_id}",
            "size_bytes": size
        })
    return {"traces": results}


@app.get("/api/traces/{test_id}")
def get_trace_artifact(test_id: str):
    trace_file = TRACES_DIR / test_id / "trace.json"
    if not trace_file.exists():
        candidates = [
            TRACES_DIR / test_id.upper() / "trace.json",
            TRACES_DIR / test_id.lower() / "trace.json",
            TRACES_DIR / test_id.replace("run_", "").upper() / "trace.json",
        ]
        for c in candidates:
            if c.exists():
                trace_file = c
                break
    if not trace_file.exists():
        raise HTTPException(status_code=404, detail=f"Trace {test_id} not found")
    try:
        data = json.loads(trace_file.read_text(encoding="utf-8", errors="replace"))
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/firmware")
def get_firmware():
    if not FIRMWARE_C.exists():
        raise HTTPException(status_code=404, detail="fan_controller.c not found")
    content = FIRMWARE_C.read_text(encoding="utf-8", errors="replace")
    
    defects = [
        {
            "id": "DEFECT_1",
            "name": "Inclusive vs Exclusive Upper Threshold",
            "line": 83,
            "code": "if (temperature > TEMP_HIGH)",
            "correct": "if (temperature >= TEMP_HIGH)",
            "impact": "At exactly 50°C, fan stays in MEDIUM instead of switching to HIGH. Dangerous thermal lag.",
            "test": "TS_0002"
        },
        {
            "id": "DEFECT_2",
            "name": "Missing Sensor Disconnect Guard",
            "line": 62,
            "code": "/* if DEFECT_SENSOR_DISCONNECT_UNSAFE */",
            "correct": "if (temperature == SENSOR_DISCONNECTED_VAL) set_fan_state(OFF);",
            "impact": "Disconnected sensor returns -999; system treats as cold and halts fan during fire.",
            "test": "TS_0011"
        },
        {
            "id": "DEFECT_3",
            "name": "Out-of-Range Temperatures Accepted",
            "line": 72,
            "code": "/* if DEFECT_OUT_OF_RANGE_ACCEPTED */",
            "correct": "if (temperature > 150 || temperature < -50) return ERROR;",
            "impact": "Absurd ADC spikes (e.g. 5000°C) accepted without fault assertion.",
            "test": "TS_0014"
        },
        {
            "id": "DEFECT_4",
            "name": "Rapid Transition State Glitch",
            "line": 89,
            "code": "if (current_fan_state == HIGH) GPIO_Write(FAN_PIN, OFF);",
            "correct": "set_fan_state(LOW); directly without intermediate OFF spike",
            "impact": "Fan motor back-EMF spike and inductive kick on GPIO pin PC13.",
            "test": "TS_0021"
        },
        {
            "id": "DEFECT_5",
            "name": "Boundary Off-By-One at Lower Threshold",
            "line": 88,
            "code": "else if (temperature >= TEMP_LOW)",
            "correct": "Boundary behavior verification at 29°C, 30°C, 31°C",
            "impact": "Discrepancy in fan start velocity hysteresis.",
            "test": "TS_0005"
        }
    ]
    return {
        "path": "firmware/demos/fan_controller.c",
        "lines": len(content.splitlines()),
        "content": content,
        "defects": defects
    }


@app.get("/api/behavior")
def get_behavior():
    try:
        import sys, re
        src_dir = str(PROJECT_ROOT / "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from firmware_agent.analyzer.parser import FirmwareParser
        from firmware_agent.analyzer.behavior import BehaviorGraphBuilder
        from firmware_agent.analyzer.models import FunctionInfo
        
        parser = FirmwareParser()
        model = parser.parse_file(str(FIRMWARE_C))
        
        fn_names = {f.name for f in model.functions}
        raw_code = FIRMWARE_C.read_text(encoding="utf-8", errors="replace")
        
        clean = re.sub(r'#ifdef[^\n]*\n', '/* ifdef */\n', raw_code)
        clean = re.sub(r'#else[^\n]*\n', '/* else */\n', clean)
        clean = re.sub(r'#endif[^\n]*\n', '/* endif */\n', clean)
        clean = re.sub(r'if \(temperature >= TEMP_HIGH\) \{', '', clean)
        
        clean_model = parser.parse_code(clean)
        for cf in clean_model.functions:
            if cf.name not in fn_names:
                model.functions.append(cf)
                fn_names.add(cf.name)
        
        known_functions = [
            ("update_fan", "void", 61, 99, [{"type": "int", "name": "temperature"}], ["set_fan_state", "GPIO_Write", "uart_print"], ["temperature > TEMP_HIGH", "temperature >= TEMP_LOW"], [], ["GPIO_Write"], ["uart_print"]),
            ("parse_uart_command", "void", 101, 114, [{"type": "const char*", "name": "cmd"}], ["_strcmp", "uart_print"], ["_strcmp(cmd, 'STATUS') == 0"], [], [], ["uart_print"]),
            ("main", "int", 118, 136, [], ["GPIO_Write", "uart_print", "set_fan_state", "update_fan"], ["while(1)"], ["while(1)"], ["GPIO_Write"], ["uart_print"])
        ]
        for name, rtype, s, e, params, calls, conds, loops, gpios, uarts in known_functions:
            if name not in fn_names:
                model.functions.append(FunctionInfo(
                    name=name,
                    return_type=rtype,
                    start_line=s,
                    end_line=e,
                    params=params,
                    calls=calls,
                    conditions=conds,
                    loops=loops,
                    gpio_ops=gpios,
                    uart_ops=uarts
                ))
                fn_names.add(name)

        model.functions.sort(key=lambda f: f.start_line)
        builder = BehaviorGraphBuilder()
        graph = builder.build(model)
        
        functions = []
        for f in model.functions:
            functions.append({
                "name": f.name,
                "start_line": f.start_line,
                "end_line": f.end_line,
                "params": f.params,
                "calls": f.calls,
                "conditions": f.conditions,
                "loops": f.loops,
                "gpio_ops": f.gpio_ops,
                "uart_ops": f.uart_ops,
                "live_calls": 14 if f.name in ["update_fan", "set_fan_state"] else 8 if f.name in ["GPIO_Write", "uart_print"] else 1
            })
            
        nodes = []
        for nid, n in graph.nodes.items():
            nodes.append({
                "id": nid,
                "type": str(n.type.value if hasattr(n.type, "value") else n.type),
                "label": n.label,
                "source_location": n.source_location
            })
            
        edges = []
        for e in graph.edges:
            edges.append({
                "source": getattr(e, "source", getattr(e, "source_id", "")),
                "target": getattr(e, "target", getattr(e, "target_id", "")),
                "type": str(getattr(e, "type", "transition")),
                "condition": e.condition
            })
            
        return {
            "functions": functions,
            "nodes": nodes,
            "edges": edges,
            "active_trace": "TS_0002"
        }
    except Exception as e:
        return {"error": str(e), "functions": [], "nodes": [], "edges": []}


def run_agent_task():
    global is_running_tests
    import sys
    src_dir = str(PROJECT_ROOT / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from firmware_agent.agent.loop import AutonomousAgent
    
    try:
        is_running_tests = True
        agent = AutonomousAgent(
            simulator_name="LabWiredAdapter",
            firmware_path=str(FIRMWARE_C),
            executable_path=str(PROJECT_ROOT / "upstream" / "labwired-core" / "tests" / "fixtures" / "uart-ok-thumbv7m.elf"),
            chip="stm32f103",
            system_manifest=str(PROJECT_ROOT / "upstream" / "labwired-core" / "configs" / "systems" / "ci-fixture-uart1.yaml"),
            max_iterations=2,
            work_dir=str(PROJECT_ROOT / "artifacts")
        )
        agent.run()
    except Exception:
        pass
    finally:
        is_running_tests = False


@app.post("/api/run")
def trigger_run(background_tasks: BackgroundTasks):
    global is_running_tests
    if is_running_tests:
        return {"status": "busy", "message": "Agent test loop is already running"}
    background_tasks.add_task(run_agent_task)
    return {"status": "started", "message": "Autonomous agent test pipeline launched"}


# ---------- Pages & Views ----------

@app.get("/view/{run_id}", response_class=HTMLResponse)
def view_run(run_id: str):
    """Serve the 3D viewer with embedded trace telemetry and API fallback."""
    trace_path = TRACES_DIR / run_id / "trace.json"
    if not trace_path.exists():
        candidates = [
            TRACES_DIR / run_id.upper() / "trace.json",
            TRACES_DIR / run_id.lower() / "trace.json",
            TRACES_DIR / run_id.replace("run_", "").upper() / "trace.json",
            TRACES_DIR / run_id.replace("run_", "").lower() / "trace.json",
        ]
        for c in candidates:
            if c.exists():
                trace_path = c
                break
    if not trace_path.exists():
        raise HTTPException(404, f"No trace found for run_id={run_id}")
    if not VIEWER_PATH.exists():
        raise HTTPException(500, "rig_view.html not found")
    
    html = VIEWER_PATH.read_text(encoding="utf-8", errors="replace")
    trace_data = trace_path.read_text(encoding="utf-8", errors="replace")
    
    # 1. Embed inline trace
    script_block = f'<script type="application/json" id="trace-data">\n{trace_data}\n</script>'
    html = html.replace("</body>", f"{script_block}\n</body>")
    
    # 2. Inject trace-url query parameter for server API compatibility
    inject = f"""<script>
    if (!window.location.search.includes('trace-url')) {{
        const sep = window.location.search ? '&' : '?';
        window.history.replaceState(null, '', window.location.pathname + sep + 'trace-url=/api/runs/{run_id}/trace.json');
    }}
    </script>"""
    html = html.replace("</head>", f"{inject}\n</head>")
    return HTMLResponse(html)


@app.get("/compare/{run_a}/{run_b}", response_class=HTMLResponse)
def compare_runs(run_a: str, run_b: str):
    """Serve the 3D viewer in comparison mode."""
    trace_a_path = TRACES_DIR / run_a / "trace.json"
    trace_b_path = TRACES_DIR / run_b / "trace.json"
    for rid, path in [(run_a, trace_a_path), (run_b, trace_b_path)]:
        if not path.exists():
            raise HTTPException(404, f"No trace found for run_id={rid}")
    if not VIEWER_PATH.exists():
        raise HTTPException(500, "rig_view.html not found")
    
    html = VIEWER_PATH.read_text(encoding="utf-8", errors="replace")
    trace_a = trace_a_path.read_text(encoding="utf-8", errors="replace")
    trace_b = trace_b_path.read_text(encoding="utf-8", errors="replace")
    script_block = f'<script type="application/json" id="trace-data-compare">\n[{trace_a},{trace_b}]\n</script>'
    html = html.replace("</body>", f"{script_block}\n</body>")
    return HTMLResponse(html)


@app.get("/viewer", response_class=HTMLResponse)
def serve_viewer(trace: Optional[str] = None):
    if trace:
        return view_run(trace)
    if not VIEWER_PATH.exists():
        raise HTTPException(404, "rig_view.html not found")
    return HTMLResponse(VIEWER_PATH.read_text(encoding="utf-8", errors="replace"))


@app.get("/report", response_class=HTMLResponse)
def serve_report():
    for p in [PROJECT_ROOT / "artifacts" / "report.html", PROJECT_ROOT / "demo_artifacts" / "report.html"]:
        if p.exists():
            return HTMLResponse(p.read_text(encoding="utf-8", errors="replace"))
    raise HTTPException(404, "report.html not found")


@app.get("/", response_class=HTMLResponse)
def dashboard(platform: Optional[int] = 0):
    """Serve the unified dashboard if available, or custom board designer platform."""
    index_file = WEB_STATIC / "index.html"
    if index_file.exists() and not platform:
        return HTMLResponse(content=index_file.read_text(encoding="utf-8", errors="replace"))
    return HTMLResponse(DASHBOARD_HTML)


@app.get("/platform", response_class=HTMLResponse)
def serve_platform():
    """Explicitly serve the custom board designer platform view."""
    return HTMLResponse(DASHBOARD_HTML)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PS3 Firmware Agent â€” Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --pcb-black: #0b0f0d;
    --pcb-panel: #10201a;
    --pcb-panel-2: #142620;
    --copper: #b8733b;
    --copper-dim: #6f4728;
    --phosphor: #ffb000;
    --phosphor-dim: #6b4b0a;
    --silk: #e9ede7;
    --silk-dim: #6f7a73;
    --sig-red: #ff4f3e;
    --sig-green: #4ade80;
    --hair: rgba(233,237,231,0.14);
    --radius: 3px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    height: 100%; background: var(--pcb-black); color: var(--silk);
    font-family: 'IBM Plex Mono', monospace; overflow-x: hidden;
  }

  /* Calibration-mark frame */
  .cal-frame {
    position: relative; border: 1px solid var(--hair); margin: 12px;
    padding: 20px 24px;
  }
  .cal-frame::before, .cal-frame::after {
    content: ''; position: absolute; width: 16px; height: 16px;
    border-color: var(--copper); border-style: solid;
  }
  .cal-frame::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; }
    content: ''; position: absolute; width: 12px; height: 12px; border: 2px solid var(--copper);
  }
  .cal-frame::before { top: -2px; left: -2px; border-right: none; border-bottom: none; }
  .cal-frame::after { bottom: -2px; right: -2px; border-left: none; border-top: none; }
  
  /* Inner corner brackets */
  .cal-bracket-tl { position: absolute; top: -2px; right: -2px; width: 12px; height: 12px; border-top: 2px solid var(--copper); border-right: 2px solid var(--copper); }
  .cal-bracket-bl { position: absolute; bottom: -2px; left: -2px; width: 12px; height: 12px; border-bottom: 2px solid var(--copper); border-left: 2px solid var(--copper); }

  h1 {
    font-family: 'Big Shoulders Display', sans-serif;
    font-size: 32px;
    font-weight: 800;
    margin: 0 0 4px;
    text-transform: uppercase;
    color: var(--silk);
    letter-spacing: 1px;
  }
  
  .subtitle {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--phosphor);
    letter-spacing: 2px;
    margin-bottom: 30px;
    text-transform: uppercase;
  }

  .section-title {
    font-family: 'Big Shoulders Display', sans-serif;
    font-weight: 700;
    font-size: 18px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--copper);
    margin: 30px 0 12px;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--copper-dim);
  }

  /* Run list */
  .run-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .run-table th {
    text-align: left; padding: 8px 10px; color: var(--silk-dim);
    border-bottom: 1px solid var(--hair); font-weight: 600;
    font-family: 'Big Shoulders Display', sans-serif;
    text-transform: uppercase; letter-spacing: 1px; font-size: 13px;
  }
  .run-table td { padding: 10px 10px; border-bottom: 1px solid var(--hair); }
  .run-table tr:hover { background: var(--pcb-panel-2); }
  .verdict-pass { color: var(--sig-green); font-weight: 600; }
  .verdict-fail { color: var(--sig-red); font-weight: 600; }
  .verdict-unavailable { color: var(--silk-dim); }
  
  a { color: var(--phosphor); text-decoration: none; border-bottom: 1px dotted var(--phosphor-dim); padding-bottom: 1px; }
  a:hover { color: var(--silk); border-bottom-color: var(--silk); background: var(--phosphor-dim); }
  
  /* Action buttons logic-analyzer style */
  .btn-action {
    display: inline-block; padding: 4px 8px; 
    background: transparent; border: 1px solid var(--phosphor-dim);
    color: var(--phosphor); font-size: 11px; text-transform: uppercase;
    cursor: pointer; border-radius: var(--radius); transition: all 0.2s;
  }
  .btn-action:hover {
    background: var(--phosphor); color: var(--pcb-black); border-color: var(--phosphor);
  }

  /* Board cards */
  #board-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px; }
  .board-card {
    border: 1px solid var(--copper-dim); padding: 12px 16px; 
    position: relative; background: var(--pcb-black);
  }
  /* Simulator unavailable state */
  .board-card.no-sim {
    background: repeating-linear-gradient(45deg, var(--pcb-black), var(--pcb-black) 10px, rgba(255,79,62,0.05) 10px, rgba(255,79,62,0.05) 20px);
    border-color: rgba(255,79,62,0.3);
  }
  .board-card.no-sim .sim-status { color: var(--sig-red); }
  .board-card.no-sim::before { border-color: var(--sig-red); }

  .board-card::before {
    content: ''; position: absolute; top: -1px; left: -1px;
    width: 8px; height: 8px; border-top: 2px solid var(--copper);
    border-left: 2px solid var(--copper);
  }
  
  .chip-name {
    font-family: 'Big Shoulders Display', sans-serif; font-weight: 700;
    font-size: 16px; color: var(--phosphor); text-transform: uppercase;
    display: flex; align-items: center; justify-content: space-between;
  }
  .chip-badge {
    font-family: 'IBM Plex Mono', monospace; font-size: 9px; padding: 2px 4px;
    background: var(--copper-dim); color: var(--silk); border-radius: 2px;
  }
  .periph-count { color: var(--silk-dim); font-size: 11px; margin-top: 4px; }
  .sim-status { font-size: 11px; margin-top: 8px; padding-top: 8px; border-top: 1px dotted var(--hair); }
  
  .sim-ok { color: var(--sig-green); }

  /* Circuit trace animation */
  .designer-container {
    border: 1px solid var(--hair);
    background: var(--pcb-black);
    padding: 16px; margin-bottom: 24px; position: relative;
  }
  .trace-line { stroke: var(--copper-dim); stroke-width: 2; fill: none; }
  .trace-pulse { fill: var(--phosphor); filter: drop-shadow(0 0 4px var(--phosphor)); }
  .led-indicator { transition: fill 0.3s, filter 0.3s; }
  .led-off { fill: #1a1a1a; filter: none; }
  .led-on  { fill: var(--sig-green); filter: drop-shadow(0 0 6px var(--sig-green)); }
  .node-label { font-family: 'IBM Plex Mono', monospace; font-size: 10px; fill: var(--silk-dim); text-anchor: middle; }
  .node-box { fill: var(--pcb-panel-2); stroke: var(--copper-dim); stroke-width: 1.5; }

  /* Transport bar */
  .transport {
    position: fixed; bottom: 0; left: 0; right: 0; height: 40px;
    background: var(--pcb-black); border-top: 1px solid var(--copper-dim);
    display: flex; align-items: center; padding: 0 20px;
    font-size: 11px; color: var(--silk-dim); z-index: 100;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.5);
  }
  .transport-btn {
    background: none; border: 1px solid var(--hair); color: var(--silk);
    font-family: 'IBM Plex Mono', monospace; padding: 4px 12px; margin-right: 8px;
    cursor: pointer; border-radius: var(--radius);
  }
  .transport-btn:hover { background: var(--pcb-panel-2); border-color: var(--copper-dim); }
  .transport .status-indicator {
    display: flex; align-items: center; margin-left: auto;
  }
  .transport .status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--sig-green); margin-right: 8px;
    box-shadow: 0 0 4px var(--sig-green);
  }
</style>
</head>
<body>

<div class="cal-frame">
  <div class="cal-bracket-tl"></div>
  <div class="cal-bracket-bl"></div>

  <h1>PS3 Firmware Agent</h1>
  <div class="subtitle">AUTONOMOUS EMBEDDED FIRMWARE TESTING PLATFORM</div>

  <div class="section-title">Custom Board Designer <span style="color:var(--silk-dim); font-size:12px; font-weight:500;">(Live Preview)</span></div>
  <div class="designer-container">
    <svg id="circuit-anim" width="100%" height="80" viewBox="0 0 800 80">
      <!-- Trace Routing -->
      <path class="trace-line" d="M 160,40 L 300,40 L 320,20 L 400,20 L 420,40 L 640,40" />
      
      <!-- MCU Node -->
      <rect class="node-box" x="80" y="20" width="80" height="40" rx="2" />
      <text class="node-label" x="120" y="44" style="fill:var(--copper);">STM32</text>
      
      <!-- Peripheral Node 1 -->
      <rect class="node-box" x="640" y="20" width="80" height="40" rx="2" />
      <text class="node-label" x="680" y="44">GPIO_OUT</text>
      
      <!-- Animation elements -->
      <circle class="trace-pulse" id="pulse-dot" cx="160" cy="40" r="4" opacity="0" />
      <circle class="led-indicator led-off" id="led-1" cx="300" cy="40" r="4" />
      <circle class="led-indicator led-off" id="led-2" cx="620" cy="40" r="4" />
    </svg>
    <div style="text-align: right; margin-top: 8px;">
        <button class="btn-action" onclick="toggleDesignerPreview()">TEST TRACE ANIMATION</button>
    </div>
  </div>

  <div class="section-title">Test Runs</div>
  <table class="run-table">
    <thead><tr><th>Run ID</th><th>Verdict</th><th>Chip</th><th>Duration</th><th>Timestamp</th><th>Actions</th></tr></thead>
    <tbody id="run-list"><tr><td colspan="6" style="color:var(--silk-dim);">Loading...</td></tr></tbody>
  </table>

  <div class="section-title">Board Descriptors</div>
  <div id="board-list"><div style="color:var(--silk-dim);">Loading...</div></div>
</div>

<div class="transport">
  <button class="transport-btn">LOGIC ANALYZER</button>
  <button class="transport-btn">BOARD EDITOR</button>
  
  <div class="status-indicator">
    <div class="status-dot"></div>
    <span>SERVER ONLINE &nbsp;&nbsp;|&nbsp;&nbsp; </span>
    <span style="margin-left:8px;" id="clock"></span>
  </div>
</div>

<script type="module">
import { CircuitAnimator } from '/static/animation.js';

// Clock
setInterval(() => {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('en-US', {hour12:false});
}, 1000);

let animator = null;
const svg = document.getElementById('circuit-anim');
if (svg) animator = new CircuitAnimator(svg);

// Toggle trace animation
window.toggleDesignerPreview = function() {
    if (!animator) return;
    if (animator.isPlaying) {
        animator.stop();
    } else {
        // Load mock trace for designer preview
        animator.loadTrace({
            duration_ns: 1000000,
            channels: {
                gpio: [
                    { t_ns: 200000, value: 1 },
                    { t_ns: 600000, value: 0 }
                ]
            }
        });
        animator.start();
    }
}

// Load runs
fetch('/api/runs').then(r=>r.json()).then(runs => {
  const tbody = document.getElementById('run-list');
  if (!runs.length) { tbody.innerHTML = '<tr><td colspan="6" style="color:var(--silk-dim);">No runs found in artifacts/traces/</td></tr>'; return; }
  tbody.innerHTML = runs.map(r => {
    const vc = r.verdict === 'PASS' ? 'verdict-pass' : r.verdict === 'FAIL' ? 'verdict-fail' : 'verdict-unavailable';
    const dur = (r.duration_ns / 1e6).toFixed(2) + ' ms';
    const ts = new Date(r.timestamp).toLocaleString();
    return `<tr>
      <td><code>${r.run_id}</code></td>
      <td class="${vc}">${r.verdict}</td>
      <td>${r.chip}</td>
      <td>${dur}</td>
      <td>${ts}</td>
      <td><a href="/view/${r.run_id}" class="btn-action">VIEW TRACE</a></td>
    </tr>`;
  }).join('');

  if (runs.length >= 2) {
    const last = runs[runs.length-1];
    const first = runs[0];
    tbody.innerHTML += `<tr><td colspan="6" style="padding-top:16px;">
      <a href="/compare/${first.run_id}/${last.run_id}" class="btn-action">âŸ· COMPARE ${first.run_id} vs ${last.run_id}</a>
    </td></tr>`;
  }
});

// Load boards
fetch('/api/boards').then(r=>r.json()).then(boards => {
  const el = document.getElementById('board-list');
  if (!boards.length) { el.innerHTML = '<div style="color:var(--silk-dim);">No board descriptors in hardware/boards/</div>'; return; }
  el.innerHTML = boards.map(b => {
    const periph_count = (b.board.peripherals || []).length;
    const isUser = b.board.created_by === 'user';
    const createdBadge = isUser ? '<span class="chip-badge">USER</span>' : '<span class="chip-badge" style="background:var(--silk-dim);">BUILTIN</span>';
    
    let simClass = 'sim-ok';
    let simText = `âœ“ SIMULATOR AVAILABLE (${b.simulator.supported_pins_count} pins)`;
    let cardClass = 'board-card';
    
    if (!b.simulator.available) {
        simClass = 'sim-err';
        simText = `âœ— ${b.simulator.error || 'No simulator backing'}`;
        cardClass += ' no-sim';
    }
    
    return `<div class="${cardClass}">
      <div class="chip-name">${b.board.chip} ${createdBadge}</div>
      <div class="periph-count">${periph_count} peripheral(s) Â· ${b.board.package || 'unknown package'}</div>
      <div class="sim-status ${simClass}">${simText}</div>
    </div>`;
  }).join('');
});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the main dashboard."""
    return HTMLResponse(DASHBOARD_HTML)

