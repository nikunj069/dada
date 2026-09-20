import os
import json
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BOARDS_DIR = BASE_DIR / "hardware" / "boards"
FIRMWARE_DIR = BASE_DIR / "firmware" / "demos"
BOARDS_DIR.mkdir(parents=True, exist_ok=True)
FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)

import os
import json
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BOARDS_DIR = BASE_DIR / "hardware" / "boards"
FIRMWARE_DIR = BASE_DIR / "firmware" / "demos"
BOARDS_DIR.mkdir(parents=True, exist_ok=True)
FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)

CHIPS = {
    "stm32f103": ["PA0", "PA1", "PA2", "PA3", "PB0", "PB1", "PC13"],
    "nrf52840": ["P0.11", "P0.12", "P0.13", "P0.14", "P1.01", "P1.02"],
    "esp32": ["P0", "P2", "P4", "P5", "P12", "P13", "P14", "P15"],
    "atsamd21g18a": ["PA02", "PA04", "PA05", "PB08", "PB09"]
}

SENSORS = [
    {"name": "Temperature", "id": "TEMP_SENS"},
    {"name": "Voltage", "id": "VOLT_SENS"},
    {"name": "Current", "id": "CURR_SENS"},
    {"name": "PIR_Motion", "id": "PIR_SENS"},
    {"name": "Gas", "id": "GAS_SENS"},
    {"name": "Moisture", "id": "MOISTURE_SENS"},
    {"name": "Pressure", "id": "PRESSURE_SENS"},
    {"name": "Light", "id": "LIGHT_SENS"},
    {"name": "Distance", "id": "DIST_SENS"},
    {"name": "Acceleration", "id": "ACCEL_SENS"},
    {"name": "Gyroscope", "id": "GYRO_SENS"},
    {"name": "Magnetic", "id": "MAG_SENS"},
    {"name": "Humidity", "id": "HUMIDITY_SENS"},
    {"name": "Sound", "id": "SOUND_SENS"},
    {"name": "HallEffect", "id": "HALL_SENS"}
]

ACTUATORS = [
    {"name": "LED_Indicator", "id": "IND_LED", "kind": "led", "cmd": "LED"},
    {"name": "Cooling_Fan", "id": "FAN_MOTOR", "kind": "motor", "cmd": "FAN"},
    {"name": "Drive_Motor", "id": "DRIVE_MOTOR", "kind": "motor", "cmd": "MOTOR"},
    {"name": "Power_Relay", "id": "PWR_RELAY", "kind": "led", "cmd": "RELAY"}, # using led logic for simple on/off visual
    {"name": "Alarm_Buzzer", "id": "ALARM_BUZZ", "kind": "led", "cmd": "BUZZER"},
    {"name": "Heater", "id": "HEAT_COIL", "kind": "led", "cmd": "HEATER"},
    {"name": "Water_Pump", "id": "WTR_PUMP", "kind": "motor", "cmd": "PUMP"},
    {"name": "Warning_Light", "id": "WARN_LED", "kind": "led", "cmd": "WARN_LGT"}
]

LOGICS = [
    {"type": "Threshold_High", "cmp": ">=", "desc": "Activates when {s} is high."},
    {"type": "Threshold_Low", "cmp": "<", "desc": "Activates when {s} drops too low."}
]

def generate_board(board_id):
    sens = random.choice(SENSORS)
    act = random.choice(ACTUATORS)
    log = random.choice(LOGICS)
    chip = random.choice(list(CHIPS.keys()))
    
    pins = random.sample(CHIPS[chip], 2)
    s_pin, a_pin = pins[0], pins[1]
    
    arch_type = f"{sens['name']}2{act['name']}_{log['type']}"
    desc = log["desc"].format(s=sens["name"].lower())
    
    board = {
        "chip": chip,
        "package": "generic",
        "board_name": f"GenBoard {board_id:03d} - {arch_type}",
        "created_by": "generator",
        "peripherals": [
            {"id": sens["id"], "kind": "sensor", "pins": [s_pin], "label": f"{sens['name']} Sensor"},
            {"id": act["id"], "kind": act["kind"], "pins": [a_pin], "label": act["name"].replace("_", " ")}
        ]
    }
    
    board_file = BOARDS_DIR / f"gen_{board_id:03d}_{chip}.json"
    board_file.write_text(json.dumps(board, indent=2))
    
    thresh = random.randint(20, 80)
    
    c_code = f"""#include "system.h"
#define THRESHOLD {thresh}

int sensor_value = 0;

void process_logic(int val) {{
    if (val {log['cmp']} THRESHOLD) {{
        GPIO_Write(PIN_{a_pin}, 1);
        uart_print("{act['cmd']} ON\\n");
    }} else {{
        GPIO_Write(PIN_{a_pin}, 0);
        uart_print("{act['cmd']} OFF\\n");
    }}
}}

int main() {{
    while(1) {{
        sensor_value = read_sensor(PIN_{s_pin});
        process_logic(sensor_value);
    }}
    return 0;
}}
"""
    c_file = FIRMWARE_DIR / f"gen_{board_id:03d}_{chip}.c"
    c_file.write_text(c_code)
    
    return board_file.name, c_file.name, chip, arch_type, desc

if __name__ == "__main__":
    print("Generating 100 uniquely combined embedded systems...")
    index_data = []
    
    for i in range(1, 101):
        b_name, c_name, chip, arch, desc = generate_board(i)
        index_data.append({
            "id": f"gen_{i:03d}_{chip}",
            "board": b_name,
            "firmware": c_name,
            "chip": chip,
            "archetype": arch,
            "description": desc
        })
        
    (BASE_DIR / "web" / "static" / "library_index.json").write_text(json.dumps(index_data, indent=2))
    print("Generation complete. 100 uniquely combined archetypes created.")
