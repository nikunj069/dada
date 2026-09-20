#include "system.h"
#define THRESHOLD 79

int sensor_value = 0;

void process_logic(int val) {
    if (val < THRESHOLD) {
        GPIO_Write(PIN_PA02, 1);
        uart_print("HEATER ON\n");
    } else {
        GPIO_Write(PIN_PA02, 0);
        uart_print("HEATER OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_PA04);
        process_logic(sensor_value);
    }
    return 0;
}
