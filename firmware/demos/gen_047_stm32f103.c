#include "system.h"
#define THRESHOLD 20

int sensor_value = 0;

void process_logic(int val) {
    if (val < THRESHOLD) {
        GPIO_Write(PIN_PA2, 1);
        uart_print("RELAY ON\n");
    } else {
        GPIO_Write(PIN_PA2, 0);
        uart_print("RELAY OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_PA1);
        process_logic(sensor_value);
    }
    return 0;
}
