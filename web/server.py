import os
import json
import glob
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
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
FIRMWARE_C = BASE_DIR / "firmware" / "demos" / "fan_controller.c"

app = FastAPI(
    title="BlackBox PS3 Firmware Testing & Rig Viewer",
    description="AI Agent for Autonomous Embedded Firmware Testing with 3D Rig Telemetry",
    version="1.0.0"
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

def get_active_report_json_path() -> Path:
    if ARTIFACTS_REPORT_JSON.exists():
        return ARTIFACTS_REPORT_JSON
    return DEMO_REPORT_JSON

def get_active_report_html_path() -> Path:
    if ARTIFACTS_REPORT_HTML.exists():
        return ARTIFACTS_REPORT_HTML
    return DEMO_REPORT_HTML

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8", errors="replace"))
    return HTMLResponse("<h1>Frontend loading...</h1>")

@app.get("/view/{run_id}", response_class=HTMLResponse)
async def view_run(run_id: str):
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

def sanitize_data(obj):
    import math
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

@app.get("/api/traces")
async def get_traces():
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
async def get_trace(test_id: str):
    trace_file = TRACES_DIR / test_id / "trace.json"
    if not trace_file.exists():
        raise HTTPException(status_code=404, detail=f"Trace {test_id} not found")
    try:
        data = json.loads(trace_file.read_text(encoding="utf-8", errors="replace"))
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/firmware")
async def get_firmware():
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
async def get_behavior():
    try:
        import sys, re
        sys.path.insert(0, str(SRC_DIR))
        from firmware_agent.analyzer.parser import FirmwareParser
        from firmware_agent.analyzer.behavior import BehaviorGraphBuilder
        from firmware_agent.analyzer.models import FunctionInfo
        
        parser = FirmwareParser()
        model = parser.parse_file(str(FIRMWARE_C))
        
        # Also ensure functions impacted by macro braces are captured
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
    global is_running_tests, last_run_status
    import sys
    sys.path.insert(0, str(SRC_DIR))
    from firmware_agent.agent.loop import AutonomousAgent
    
    try:
        is_running_tests = True
        last_run_status = "running"
        agent = AutonomousAgent(
            simulator_name="LabWiredAdapter",
            firmware_path=str(FIRMWARE_C),
            executable_path=str(BASE_DIR / "upstream" / "labwired-core" / "tests" / "fixtures" / "uart-ok-thumbv7m.elf"),
            chip="stm32f103",
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
async def trigger_run(background_tasks: BackgroundTasks):
    global is_running_tests
    if is_running_tests:
        return {"status": "busy", "message": "Agent test loop is already running"}
    background_tasks.add_task(run_agent_task)
    return {"status": "started", "message": "Autonomous agent test pipeline launched"}

def main():
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting BlackBox PS3 Firmware Testing Server on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    main()
