#include "system.h"
#define THRESHOLD 43

int sensor_value = 0;

void process_logic(int val) {
    if (val >= THRESHOLD) {
        GPIO_Write(PIN_P0.14, 1);
        uart_print("BUZZER ON\n");
    } else {
        GPIO_Write(PIN_P0.14, 0);
        uart_print("BUZZER OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_P1.01);
        process_logic(sensor_value);
    }
    return 0;
}
