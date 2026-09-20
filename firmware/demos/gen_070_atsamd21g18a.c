#include "system.h"
#define TEMP_HIGH 52

int temperature = 0;

void update_fan(int t) {
    if (t >= TEMP_HIGH) {
        GPIO_Write(PIN_PA02, 1);
        uart_print("FAN ON\n");
    } else {
        GPIO_Write(PIN_PA02, 0);
        uart_print("FAN OFF\n");
    }
}

int main() {
    while(1) {
        temperature = read_sensor(PIN_PB09);
        update_fan(temperature);
    }
    return 0;
}
