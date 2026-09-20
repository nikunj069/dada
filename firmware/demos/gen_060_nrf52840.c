#include "system.h"
#define TEMP_HIGH 77

int temperature = 0;

void update_fan(int t) {
    if (t >= TEMP_HIGH) {
        GPIO_Write(PIN_P0.11, 1);
        uart_print("FAN ON\n");
    } else {
        GPIO_Write(PIN_P0.11, 0);
        uart_print("FAN OFF\n");
    }
}

int main() {
    while(1) {
        temperature = read_sensor(PIN_P1.02);
        update_fan(temperature);
    }
    return 0;
}
