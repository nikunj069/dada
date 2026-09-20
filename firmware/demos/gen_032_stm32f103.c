#include "system.h"
#define THRESHOLD 54

int sensor_value = 0;

void process_logic(int val) {
    if (val >= THRESHOLD) {
        GPIO_Write(PIN_PB1, 1);
        uart_print("MOTOR ON\n");
    } else {
        GPIO_Write(PIN_PB1, 0);
        uart_print("MOTOR OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_PA0);
        process_logic(sensor_value);
    }
    return 0;
}
