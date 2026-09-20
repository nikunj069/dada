#include "system.h"
#define THRESHOLD 36

int sensor_value = 0;

void process_logic(int val) {
    if (val >= THRESHOLD) {
        GPIO_Write(PIN_PA04, 1);
        uart_print("PUMP ON\n");
    } else {
        GPIO_Write(PIN_PA04, 0);
        uart_print("PUMP OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_PA05);
        process_logic(sensor_value);
    }
    return 0;
}
