#include "system.h"
#define THRESHOLD 68

int sensor_value = 0;

void process_logic(int val) {
    if (val < THRESHOLD) {
        GPIO_Write(PIN_PA0, 1);
        uart_print("FAN ON\n");
    } else {
        GPIO_Write(PIN_PA0, 0);
        uart_print("FAN OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_PB0);
        process_logic(sensor_value);
    }
    return 0;
}
