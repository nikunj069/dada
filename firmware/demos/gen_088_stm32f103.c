#include "system.h"
#define THRESHOLD 26

int sensor_value = 0;

void process_logic(int val) {
    if (val >= THRESHOLD) {
        GPIO_Write(PIN_PA3, 1);
        uart_print("RELAY ON\n");
    } else {
        GPIO_Write(PIN_PA3, 0);
        uart_print("RELAY OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_PC13);
        process_logic(sensor_value);
    }
    return 0;
}
