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

ARCHETYPES = [
    {
        "type": "TemperatureController",
        "desc": "Monitors temperature and controls a fan.",
        "peripherals": [
            {"id": "TEMP_SENS", "kind": "sensor"},
            {"id": "FAN_MOTOR", "kind": "motor"}
        ],
        "c_template": """#include "system.h"
#define TEMP_HIGH {thresh}

int temperature = 0;

void update_fan(int t) {
    if (t >= TEMP_HIGH) {
        GPIO_Write({p_motor}, 1);
        uart_print("FAN ON\\n");
    } else {
        GPIO_Write({p_motor}, 0);
        uart_print("FAN OFF\\n");
    }
}

int main() {
    while(1) {
        temperature = read_sensor({p_sens});
        update_fan(temperature);
    }
    return 0;
}
"""
    },
    {
        "type": "VoltageDropper",
        "desc": "Detects undervoltage and asserts alarm.",
        "peripherals": [
            {"id": "V_MONITOR", "kind": "sensor"},
            {"id": "ALARM_LED", "kind": "led"}
        ],
        "c_template": """#include "system.h"
#define V_MIN {thresh}

int voltage = 0;

void check_voltage(int v) {
    if (v < V_MIN) {
        GPIO_Write({p_led}, 1);
        uart_print("UNDERVOLTAGE\\n");
    } else {
        GPIO_Write({p_led}, 0);
        uart_print("V OK\\n");
    }
}

int main() {
    while(1) {
        voltage = read_sensor({p_sens});
        check_voltage(voltage);
    }
    return 0;
}
"""
    },
    {
        "type": "AudioAmplifier",
        "desc": "Simulated audio signal amplifier with clipping.",
        "peripherals": [
            {"id": "AUDIO_IN", "kind": "sensor"},
            {"id": "SPEAKER", "kind": "motor"},
            {"id": "CLIP_LED", "kind": "led"}
        ],
        "c_template": """#include "system.h"
#define CLIP_LIMIT {thresh}

int audio = 0;

void process_audio(int a) {
    if (a > CLIP_LIMIT || a < -CLIP_LIMIT) {
        GPIO_Write({p_led}, 1); // Clipping indicator
        uart_print("CLIP\\n");
        GPIO_Write({p_motor}, 1); // Distorted output
    } else {
        GPIO_Write({p_led}, 0);
        uart_print("AUDIO OK\\n");
        GPIO_Write({p_motor}, a > 0 ? 1 : 0); // Simplified PWM
    }
}

int main() {
    while(1) {
        audio = read_sensor({p_sens});
        process_audio(audio);
    }
    return 0;
}
"""
    }
]

def generate_board(board_id):
    arch = random.choice(ARCHETYPES)
    chip = random.choice(list(CHIPS.keys()))
    pins = random.sample(CHIPS[chip], len(arch["peripherals"]))
    
    board = {
        "chip": chip,
        "package": "generic",
        "board_name": f"GenBoard {board_id:03d} - {arch['type']}",
        "created_by": "generator",
        "peripherals": []
    }
    
    mapping = {}
    for i, periph in enumerate(arch["peripherals"]):
        p_pin = pins[i]
        mapping[periph["id"]] = p_pin
        board["peripherals"].append({
            "id": periph["id"],
            "kind": periph["kind"],
            "pins": [p_pin]
        })
        
    board_file = BOARDS_DIR / f"gen_{board_id:03d}_{chip}.json"
    board_file.write_text(json.dumps(board, indent=2))
    
    # Generate C Code
    thresh = random.randint(10, 80)
    c_code = arch["c_template"]
    c_code = c_code.replace("{thresh}", str(thresh))
    
    for pid, p_pin in mapping.items():
        if "SENS" in pid or "IN" in pid or "MONITOR" in pid:
            c_code = c_code.replace("{p_sens}", f"PIN_{p_pin}")
        elif "MOTOR" in pid or "SPEAKER" in pid:
            c_code = c_code.replace("{p_motor}", f"PIN_{p_pin}")
        elif "LED" in pid or "ALARM" in pid:
            c_code = c_code.replace("{p_led}", f"PIN_{p_pin}")
            
    c_file = FIRMWARE_DIR / f"gen_{board_id:03d}_{chip}.c"
    c_file.write_text(c_code)
    
    return board_file.name, c_file.name, chip, arch['type']

if __name__ == "__main__":
    print("Generating 100 embedded systems...")
    generated = []
    
    # Generate an index file for the UI to consume
    index_data = []
    
    for i in range(1, 101):
        b_name, c_name, chip, arch = generate_board(i)
        generated.append((b_name, c_name, chip))
        index_data.append({
            "id": f"gen_{i:03d}_{chip}",
            "board": b_name,
            "firmware": c_name,
            "chip": chip,
            "archetype": arch
        })
        
    (BASE_DIR / "web" / "static" / "library_index.json").write_text(json.dumps(index_data, indent=2))
    print("Generation complete. Wrote library_index.json for UI.")
