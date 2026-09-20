#include "system.h"
#define THRESHOLD 28

int sensor_value = 0;

void process_logic(int val) {
    if (val < THRESHOLD) {
        GPIO_Write(PIN_PB0, 1);
        uart_print("LED ON\n");
    } else {
        GPIO_Write(PIN_PB0, 0);
        uart_print("LED OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_PB1);
        process_logic(sensor_value);
    }
    return 0;
}
