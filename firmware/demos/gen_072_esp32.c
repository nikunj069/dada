#include "system.h"
#define THRESHOLD 35

int sensor_value = 0;

void process_logic(int val) {
    if (val < THRESHOLD) {
        GPIO_Write(PIN_P5, 1);
        uart_print("PUMP ON\n");
    } else {
        GPIO_Write(PIN_P5, 0);
        uart_print("PUMP OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_P12);
        process_logic(sensor_value);
    }
    return 0;
}
