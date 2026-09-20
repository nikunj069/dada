#include "system.h"
#define TEMP_HIGH 49

int temperature = 0;

void update_fan(int t) {
    if (t >= TEMP_HIGH) {
        GPIO_Write(PIN_PA04, 1);
        uart_print("FAN ON\n");
    } else {
        GPIO_Write(PIN_PA04, 0);
        uart_print("FAN OFF\n");
    }
}

int main() {
    while(1) {
        temperature = read_sensor(PIN_PA02);
        update_fan(temperature);
    }
    return 0;
}
