#include "system.h"
#define THRESHOLD 44

int sensor_value = 0;

void process_logic(int val) {
    if (val >= THRESHOLD) {
        GPIO_Write(PIN_P12, 1);
        uart_print("HEATER ON\n");
    } else {
        GPIO_Write(PIN_P12, 0);
        uart_print("HEATER OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_P0);
        process_logic(sensor_value);
    }
    return 0;
}
