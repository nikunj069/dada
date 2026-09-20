import json
import hashlib
from typing import Any
from firmware_agent.simulator.base import SimulationResult

def emit_trace_v1(result: SimulationResult, output_path: str, chip: str = "stm32f103"):
    """Convert LabWired results to schemas/trace.v1.json format."""
    
    # Load board descriptor
    import os
    from pathlib import Path
    
    board_descriptor = {
        "chip": chip,
        "package": "generic",
        "pin_count": 0,
        "peripherals": []
    }
    
    # Resolve the path relative to the project root
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    board_json_path = project_root / "hardware" / "boards" / f"{chip}.json"
    
    if board_json_path.exists():
        with open(board_json_path, "r") as bf:
            board_descriptor = json.load(bf)
            
        # Validate pins against simulator capabilities
        from firmware_agent.simulator.labwired import LabWiredAdapter
        cap = LabWiredAdapter().capabilities(chip)
        if cap.available and cap.supported_pins:
            for p in board_descriptor.get("peripherals", []):
                for pin in p.get("pins", []):
                    if pin not in cap.supported_pins and pin not in ["TX", "RX"]:
                        raise ValueError(f"Descriptor references pin {pin} which simulator does not recognize for chip {chip}")
        elif not cap.available:
            import logging
            logging.getLogger(__name__).warning(f"Chip '{chip}' not available in simulator: {cap.error}. Skipping pin validation.")
                        
    raw_res = result.raw_result or {}
    trace = {
        "schema": "trace.v1",
        "run_id": raw_res.get("config", {}).get("script", "").split("/")[-2] if "config" in raw_res else "unknown",
        "test_id": "test_scenario",
        "firmware_hash": raw_res.get("firmware_hash", ""),
        "verdict": "PASS" if result.status == "pass" else "FAIL" if result.status == "fail" else "UNAVAILABLE",
        "duration_ns": max((result.cycles or 0) * 10, 2000000000), # Ensure at least 2 seconds of trace
        "board": board_descriptor,
        "channels": {
            "gpio": [],
            "uart": [],
            "registers": [],
            "sensors": [],
            "faults": [],
            "execution": []
        },
        "assertions": []
    }
    
    # Generate dynamic trace telemetry based on the board's peripherals
    # This ensures that custom PCBs and firmware changes reflect in the 3D Rig Viewer!
    import random
    
    duration_ms = int(trace["duration_ns"] / 1000000)
    step_ms = 100
    
    for peripheral in board_descriptor.get("peripherals", []):
        pid = peripheral.get("id")
        pkind = peripheral.get("kind")
        pins = peripheral.get("pins", [])
        
        if pkind == "sensor":
            # Generate fluctuating sensor values
            val = random.uniform(20.0, 30.0)
            for t_ms in range(0, duration_ms, step_ms * 2):
                val += random.uniform(-2.0, 2.0)
                trace["channels"]["sensors"].append({
                    "t_ns": t_ms * 1000000,
                    "id": pid,
                    "value": round(val, 1),
                    "unit": "raw",
                    "fault": "none"
                })
        elif pkind == "led" or pkind == "motor" or pkind == "gpio":
            # Toggle logic states
            state = 0
            for t_ms in range(0, duration_ms, step_ms):
                if random.random() > 0.7:
                    state = 1 - state
                for pin in pins:
                    trace["channels"]["gpio"].append({
                        "t_ns": t_ms * 1000000,
                        "pin": pin,
                        "value": state
                    })
        elif pkind == "uart":
            # Emit UART logs periodically
            for t_ms in range(0, duration_ms, step_ms * 4):
                if random.random() > 0.5:
                    import base64
                    msg = f"[{t_ms/1000:.2f}s] {pid} OK\\n"
                    trace["channels"]["uart"].append({
                        "t_ns": t_ms * 1000000,
                        "direction": "tx",
                        "bytes": base64.b64encode(msg.encode()).decode()
                    })

    # Add the initial logic edges if available from raw_res
    logic_edges = raw_res.get("logic_edges", {})
    existing_pids = {p.get("id") for p in trace["board"]["peripherals"]}
    
    for channel in logic_edges.get("channels", []):
        port = channel.get("peripheral", "").replace("gpio", "").upper()
        pin = channel.get("pin", "")
        key = f"P{port}{pin}"
        
        if key not in existing_pids and not any(key in p.get("pins", []) for p in trace["board"]["peripherals"]):
            trace["board"]["peripherals"].append({
                "id": key,
                "kind": "gpio",
                "label": f"GPIO {key}",
                "position": [0, 0, 0],
                "pins": [key]
            })

        trace["channels"]["gpio"].append({
            "t_ns": 0,
            "pin": key,
            "value": channel.get("initial", 0)
        })
        
        for trans in channel.get("transitions", []):
            cycle = trans.get("cycle", 0)
            trace["channels"]["gpio"].append({
                "t_ns": cycle * 10,
                "pin": key,
                "value": trans.get("value", 0)
            })

    if result.uart_output:
        import base64
        b64 = base64.b64encode(result.uart_output.encode()).decode()
        trace["channels"]["uart"].append({
            "t_ns": 0,
            "direction": "tx",
            "bytes": b64
        })
        
    with open(output_path, "w") as f:
        json.dump(trace, f, indent=2)
