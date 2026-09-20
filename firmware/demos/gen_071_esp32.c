#include "system.h"
#define THRESHOLD 79

int sensor_value = 0;

void process_logic(int val) {
    if (val < THRESHOLD) {
        GPIO_Write(PIN_P12, 1);
        uart_print("WARN_LGT ON\n");
    } else {
        GPIO_Write(PIN_P12, 0);
        uart_print("WARN_LGT OFF\n");
    }
}

int main() {
    while(1) {
        sensor_value = read_sensor(PIN_P2);
        process_logic(sensor_value);
    }
    return 0;
}
