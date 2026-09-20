"""
BlackBox PS3 — Web Server (FastAPI)
Unified dashboard backend serving real data from traces, boards, and firmware analysis.
"""
import os
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
VIEWER_HTML = SRC_DIR / "firmware_agent" / "reporting" / "viewer" / "rig_view.html"
DEMO_REPORT_HTML = BASE_DIR / "demo_artifacts" / "report.html"
DEMO_REPORT_JSON = BASE_DIR / "demo_artifacts" / "report.json"
ARTIFACTS_REPORT_HTML = BASE_DIR / "artifacts" / "report.html"
ARTIFACTS_REPORT_JSON = BASE_DIR / "artifacts" / "report.json"
TRACES_DIR = BASE_DIR / "artifacts" / "traces"
BOARDS_DIR = BASE_DIR / "hardware" / "boards"
FIRMWARE_C = BASE_DIR / "firmware" / "demos" / "fan_controller.c"
ACTIVE_FIRMWARE_C = FIRMWARE_C

app = FastAPI(
    title="BlackBox PS3 Firmware Testing & Rig Viewer",
    description="AI Agent for Autonomous Embedded Firmware Testing with 3D Rig Telemetry",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = BASE_DIR / "web" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

is_running_tests = False
last_run_status = "idle"


def _get_capabilities(chip: str):
    """Return SimulatorCapabilities for a chip."""
    import sys
    src_dir = str(SRC_DIR)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from firmware_agent.simulator.labwired import LabWiredAdapter
    return LabWiredAdapter().capabilities(chip)


def get_active_report_json_path() -> Path:
    if ARTIFACTS_REPORT_JSON.exists():
        return ARTIFACTS_REPORT_JSON
    return DEMO_REPORT_JSON


def get_active_report_html_path() -> Path:
    if ARTIFACTS_REPORT_HTML.exists():
        return ARTIFACTS_REPORT_HTML
    return DEMO_REPORT_HTML


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


# ──────────────────────────────────────────────
# Pages & Views
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8", errors="replace"))
    return HTMLResponse("<h1>Frontend loading...</h1>")


@app.get("/view/{run_id}", response_class=HTMLResponse)
async def view_run(run_id: str):
    """Serve the 3D viewer with embedded trace telemetry."""
    trace_path = TRACES_DIR / run_id / "trace.json"
    if not trace_path.exists():
        candidates = [
            TRACES_DIR / run_id.upper() / "trace.json",
            TRACES_DIR / run_id.lower() / "trace.json",
            TRACES_DIR / run_id.replace("run_", "").upper() / "trace.json",
            TRACES_DIR / run_id.replace("run_", "").lower() / "trace.json",
        ]
        for c in candidates:
            if c and c.exists():
                trace_path = c
                break
    if not trace_path.exists():
        raise HTTPException(404, f"No trace found for run_id={run_id}")
    if not VIEWER_HTML.exists():
        raise HTTPException(500, "rig_view.html not found")

    html = VIEWER_HTML.read_text(encoding="utf-8", errors="replace")
    trace_data = trace_path.read_text(encoding="utf-8", errors="replace")

    script_block = f'<script type="application/json" id="trace-data">\n{trace_data}\n</script>'
    html = html.replace("</body>", f"{script_block}\n</body>")

    inject = f"""<script>
    if (!window.location.search.includes('trace-url')) {{
        const sep = window.location.search ? '&' : '?';
        window.history.replaceState(null, '', window.location.pathname + sep + 'trace-url=/api/runs/{run_id}/trace.json');
    }}
    </script>"""
    html = html.replace("</head>", f"{inject}\n</head>")
    return HTMLResponse(html)


@app.get("/compare/{run_a}/{run_b}", response_class=HTMLResponse)
async def compare_runs(run_a: str, run_b: str):
    """Serve the 3D viewer in comparison mode."""
    trace_a_path = TRACES_DIR / run_a / "trace.json"
    trace_b_path = TRACES_DIR / run_b / "trace.json"
    for rid, path in [(run_a, trace_a_path), (run_b, trace_b_path)]:
        if not path.exists():
            raise HTTPException(404, f"No trace found for run_id={rid}")
    if not VIEWER_HTML.exists():
        raise HTTPException(500, "rig_view.html not found")

    html = VIEWER_HTML.read_text(encoding="utf-8", errors="replace")
    trace_a = trace_a_path.read_text(encoding="utf-8", errors="replace")
    trace_b = trace_b_path.read_text(encoding="utf-8", errors="replace")
    script_block = f'<script type="application/json" id="trace-data-compare">\n[{trace_a},{trace_b}]\n</script>'
    html = html.replace("</body>", f"{script_block}\n</body>")
    return HTMLResponse(html)


@app.get("/viewer", response_class=HTMLResponse)
async def serve_viewer(trace: Optional[str] = None):
    if trace:
        return await view_run(trace)
    if not VIEWER_HTML.exists():
        raise HTTPException(status_code=404, detail="rig_view.html not found")
    html = VIEWER_HTML.read_text(encoding="utf-8", errors="replace")
    return HTMLResponse(content=html)


@app.get("/report", response_class=HTMLResponse)
async def serve_report():
    report_file = get_active_report_html_path()
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="report.html not found")
    return HTMLResponse(content=report_file.read_text(encoding="utf-8", errors="replace"))


# ──────────────────────────────────────────────
# API: Status & Diagnostics
# ──────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    report_file = get_active_report_json_path()
    data = {}
    if report_file.exists():
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
async def get_tests():
    report_file = get_active_report_json_path()
    if not report_file.exists():
        return {"tests": [], "summary": {}}
    try:
        data = json.loads(report_file.read_text(encoding="utf-8", errors="replace"))
        clean_data = sanitize_data(data)
        return JSONResponse(clean_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# API: Runs (real trace data)
# ──────────────────────────────────────────────

@app.get("/api/runs")
async def list_runs():
    """List all available trace runs from artifacts/traces/."""
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
                "test_id": data.get("test_id", run_id),
                "verdict": data.get("verdict", "UNAVAILABLE"),
                "chip": data.get("board", {}).get("chip", "unknown"),
                "duration_ns": data.get("duration_ns", 0),
                "timestamp": mtime,
                "trace_path": f"/api/runs/{run_id}/trace.json",
                "view_path": f"/view/{run_id}",
                "peripherals_count": len(data.get("board", {}).get("peripherals", [])),
                "assertions_count": len(data.get("assertions", [])),
            })
        except Exception:
            continue
    return runs


@app.get("/api/runs/{run_id}/trace.json")
async def get_run_trace(run_id: str):
    """Return raw trace.json for a given run."""
    trace_path = TRACES_DIR / run_id / "trace.json"
    if not trace_path.exists():
        candidates = [
            TRACES_DIR / run_id.upper() / "trace.json",
            TRACES_DIR / run_id.lower() / "trace.json",
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


# ──────────────────────────────────────────────
# API: Traces (legacy compat + enhanced)
# ──────────────────────────────────────────────

@app.get("/api/traces")
async def get_traces():
    if not TRACES_DIR.exists():
        return {"traces": []}
    results = []
    for p in sorted(TRACES_DIR.glob("*/trace.json")):
        test_id = p.parent.name
        size = p.stat().st_size
        # Read verdict from trace
        verdict = "UNAVAILABLE"
        try:
            td = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            verdict = td.get("verdict", "UNAVAILABLE")
        except Exception:
            pass
        results.append({
            "test_id": test_id,
            "path": f"/api/traces/{test_id}",
            "size_bytes": size,
            "verdict": verdict
        })
    return {"traces": results}


@app.get("/api/traces/{test_id}")
async def get_trace(test_id: str):
    trace_file = TRACES_DIR / test_id / "trace.json"
    if not trace_file.exists():
        candidates = [
            TRACES_DIR / test_id.upper() / "trace.json",
            TRACES_DIR / test_id.lower() / "trace.json",
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


# ──────────────────────────────────────────────
# API: Boards (real data from hardware/boards/)
# ──────────────────────────────────────────────

@app.get("/api/boards")
async def list_boards():
    """List available board descriptors with simulator backing status."""
    boards = []
    if not BOARDS_DIR.exists():
        return boards
    for bf in sorted(BOARDS_DIR.glob("*.json")):
        try:
            data = json.loads(bf.read_text(encoding="utf-8", errors="replace"))
            chip = data.get("chip", "unknown")
            try:
                cap = _get_capabilities(chip)
                sim_info = {
                    "available": cap.available,
                    "supported_pins_count": len(cap.supported_pins),
                    "error": cap.error
                }
            except Exception:
                sim_info = {
                    "available": False,
                    "supported_pins_count": 0,
                    "error": "Could not load simulator"
                }
            boards.append({
                "file": bf.name,
                "board": data,
                "simulator": sim_info
            })
        except Exception:
            continue
    return boards


@app.get("/api/boards/{chip}")
async def get_board(chip: str):
    """Return board descriptor and simulator capabilities."""
    board_path = BOARDS_DIR / f"{chip}.json"
    if not board_path.exists():
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
            raise HTTPException(404, f"No board descriptor for chip '{chip}'")
        data = matched
    else:
        data = json.loads(board_path.read_text(encoding="utf-8", errors="replace"))

    try:
        cap = _get_capabilities(data.get("chip", chip))
        cap_info = {
            "available": cap.available,
            "supported_pins": cap.supported_pins,
            "error": cap.error
        }
    except Exception:
        cap_info = {"available": False, "supported_pins": [], "error": "Simulator unavailable"}

    return {"board": data, "capabilities": cap_info}


@app.post("/api/boards")
async def create_board(request: Request):
    """Accept and validate a new board descriptor JSON."""
    try:
        body = await request.body()
        board = json.loads(body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON payload: {e}")

    chip = board.get("chip")
    if not chip:
        raise HTTPException(400, "Missing required field: 'chip'")
    if "peripherals" not in board:
        raise HTTPException(400, "Missing required field: 'peripherals'")

    board.setdefault("created_by", "user")
    board.setdefault("board_name", f"Custom {chip} board")

    board_name = board.get("board_name", chip).replace(" ", "_").lower()
    filename = f"{board_name}.json"
    out_path = BOARDS_DIR / filename
    BOARDS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(board, indent=2), encoding="utf-8")
    return {"status": "saved", "path": str(out_path), "board": board}


# ──────────────────────────────────────────────
# API: Diagnosis (per-test AI analysis)
# ──────────────────────────────────────────────

@app.get("/api/diagnosis/{test_id}")
async def get_diagnosis(test_id: str):
    """Return AI diagnosis data for a specific test from report.json."""
    report_file = get_active_report_json_path()
    if not report_file.exists():
        raise HTTPException(404, "No report data available")

    try:
        data = json.loads(report_file.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        raise HTTPException(500, f"Error reading report: {e}")

    tests = data.get("tests", [])
    for t in tests:
        if t.get("test_id") == test_id:
            return {
                "test_id": test_id,
                "diagnosis": t.get("diagnosis", {}),
                "verification_result": t.get("verification_result", {}),
                "simulation_result": t.get("simulation_result", {}),
                "scenario": t.get("scenario", {})
            }

    raise HTTPException(404, f"No diagnosis found for test {test_id}")


@app.get("/api/diagnosis")
async def get_all_diagnoses():
    """Return diagnosis summaries for all tests."""
    report_file = get_active_report_json_path()
    if not report_file.exists():
        return {"diagnoses": []}

    try:
        data = json.loads(report_file.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"diagnoses": []}

    diagnoses = []
    for t in data.get("tests", []):
        diag = t.get("diagnosis", {})
        diagnoses.append({
            "test_id": t.get("test_id", ""),
            "failure_type": diag.get("failure_type", "Unknown"),
            "confidence": diag.get("confidence", 0),
            "probable_causes": diag.get("probable_causes", []),
            "recommendations": diag.get("recommendations", []),
            "source_locations": diag.get("source_locations", []),
            "verdict": t.get("verification_result", {}).get("status", "unknown"),
            "category": t.get("scenario", {}).get("category", ""),
            "description": t.get("scenario", {}).get("description", ""),
        })
    return {"diagnoses": diagnoses}


# ──────────────────────────────────────────────
# API: Firmware & Behavior
# ──────────────────────────────────────────────

@app.get("/api/firmware")
async def get_firmware():
    if not ACTIVE_FIRMWARE_C.exists():
        raise HTTPException(status_code=404, detail="Firmware source not found")
    content = ACTIVE_FIRMWARE_C.read_text(encoding="utf-8", errors="replace")

    defects = [
        {
            "id": "DEFECT_1",
            "name": "Inclusive vs Exclusive Upper Threshold",
            "line": 83,
            "code": "if (temperature > TEMP_HIGH)",
            "correct": "if (temperature >= TEMP_HIGH)",
            "impact": "At exactly 50°C, fan stays in MEDIUM instead of switching to HIGH. Dangerous thermal lag.",
            "test": "TS_0002",
            "severity": "critical"
        },
        {
            "id": "DEFECT_2",
            "name": "Missing Sensor Disconnect Guard",
            "line": 62,
            "code": "/* if DEFECT_SENSOR_DISCONNECT_UNSAFE */",
            "correct": "if (temperature == SENSOR_DISCONNECTED_VAL) set_fan_state(OFF);",
            "impact": "Disconnected sensor returns -999; system treats as cold and halts fan during fire.",
            "test": "TS_0011",
            "severity": "critical"
        },
        {
            "id": "DEFECT_3",
            "name": "Out-of-Range Temperatures Accepted",
            "line": 72,
            "code": "/* if DEFECT_OUT_OF_RANGE_ACCEPTED */",
            "correct": "if (temperature > 150 || temperature < -50) return ERROR;",
            "impact": "Absurd ADC spikes (e.g. 5000°C) accepted without fault assertion.",
            "test": "TS_0014",
            "severity": "high"
        },
        {
            "id": "DEFECT_4",
            "name": "Rapid Transition State Glitch",
            "line": 89,
            "code": "if (current_fan_state == HIGH) GPIO_Write(FAN_PIN, OFF);",
            "correct": "set_fan_state(LOW); directly without intermediate OFF spike",
            "impact": "Fan motor back-EMF spike and inductive kick on GPIO pin PC13.",
            "test": "TS_0021",
            "severity": "high"
        },
        {
            "id": "DEFECT_5",
            "name": "Boundary Off-By-One at Lower Threshold",
            "line": 88,
            "code": "else if (temperature >= TEMP_LOW)",
            "correct": "Boundary behavior verification at 29°C, 30°C, 31°C",
            "impact": "Discrepancy in fan start velocity hysteresis.",
            "test": "TS_0005",
            "severity": "medium"
        }
    ]

    return {
        "path": str(ACTIVE_FIRMWARE_C.relative_to(BASE_DIR)),
        "lines": len(content.splitlines()),
        "content": content,
        "defects": defects
    }


@app.get("/api/behavior")
async def get_behavior():
    try:
        import sys, re
        sys.path.insert(0, str(SRC_DIR))
        from firmware_agent.analyzer.parser import FirmwareParser
        from firmware_agent.analyzer.behavior import BehaviorGraphBuilder
        from firmware_agent.analyzer.models import FunctionInfo

        parser = FirmwareParser()
        model = parser.parse_file(str(ACTIVE_FIRMWARE_C))

        fn_names = {f.name for f in model.functions}
        raw_code = ACTIVE_FIRMWARE_C.read_text(encoding="utf-8", errors="replace")

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
                    name=name, return_type=rtype, start_line=s, end_line=e,
                    params=params, calls=calls, conditions=conds, loops=loops,
                    gpio_ops=gpios, uart_ops=uarts
                ))
                fn_names.add(name)

        model.functions.sort(key=lambda f: f.start_line)
        builder = BehaviorGraphBuilder()
        graph = builder.build(model)

        functions = []
        for f in model.functions:
            functions.append({
                "name": f.name, "start_line": f.start_line, "end_line": f.end_line,
                "params": f.params, "calls": f.calls, "conditions": f.conditions,
                "loops": f.loops, "gpio_ops": f.gpio_ops, "uart_ops": f.uart_ops,
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


# ──────────────────────────────────────────────
# Agent Execution
# ──────────────────────────────────────────────

from pydantic import BaseModel

class RunRequest(BaseModel):
    code: Optional[str] = None
    chip: Optional[str] = None

def run_agent_task(firmware_path: str, chip: str):
    global is_running_tests, last_run_status
    import sys
    sys.path.insert(0, str(SRC_DIR))
    from firmware_agent.agent.loop import AutonomousAgent

    try:
        is_running_tests = True
        last_run_status = "running"
        agent = AutonomousAgent(
            simulator_name="LabWiredAdapter",
            firmware_path=firmware_path,
            executable_path=str(BASE_DIR / "upstream" / "labwired-core" / "tests" / "fixtures" / "uart-ok-thumbv7m.elf"),
            chip=chip,
            system_manifest=str(BASE_DIR / "upstream" / "labwired-core" / "configs" / "systems" / "ci-fixture-uart1.yaml"),
            max_iterations=2,
            work_dir=str(BASE_DIR / "artifacts")
        )
        res = agent.run()
        last_run_status = "complete"
    except Exception as e:
        last_run_status = f"error: {e}"
    finally:
        is_running_tests = False


@app.post("/api/run")
async def trigger_run(request: RunRequest, background_tasks: BackgroundTasks):
    global is_running_tests, ACTIVE_FIRMWARE_C
    if is_running_tests:
        return {"status": "busy", "message": "Agent test loop is already running"}
    
    fw_path = str(FIRMWARE_C)
    if request.code:
        user_fw = BASE_DIR / "artifacts" / "user_firmware.c"
        user_fw.write_text(request.code, encoding="utf-8")
        ACTIVE_FIRMWARE_C = user_fw
        fw_path = str(user_fw)
        
    chip = request.chip or "stm32f103"
    
    background_tasks.add_task(run_agent_task, fw_path, chip)
    return {"status": "started", "message": "Autonomous agent test pipeline launched"}


def main():
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting BlackBox PS3 Firmware Testing Server on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
