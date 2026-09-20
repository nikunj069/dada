#include "system.h"
#define THRESHOLD 71

int sensor_value = 0;

void process_logic(int val) {
    if (val < THRESHOLD) {
        GPIO_Write(PIN_P2, 1);
        uart_print("LED ON\n");
    } else {
        GPIO_Write(PIN_P2, 0);
        uart_print("LED OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_P4);
        process_logic(sensor_value);
    }
    return 0;
}
