#include "system.h"
#define THRESHOLD 71

int sensor_value = 0;

void process_logic(int val) {
    if (val < THRESHOLD) {
        GPIO_Write(PIN_PB09, 1);
        uart_print("BUZZER ON\n");
    } else {
        GPIO_Write(PIN_PB09, 0);
        uart_print("BUZZER OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_PA02);
        process_logic(sensor_value);
    }
    return 0;
}
