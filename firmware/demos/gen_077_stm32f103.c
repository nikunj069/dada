#include "system.h"
#define THRESHOLD 67

int sensor_value = 0;

void process_logic(int val) {
    if (val >= THRESHOLD) {
        GPIO_Write(PIN_PA1, 1);
        uart_print("LED ON\n");
    } else {
        GPIO_Write(PIN_PA1, 0);
        uart_print("LED OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_PA0);
        process_logic(sensor_value);
    }
    return 0;
}
