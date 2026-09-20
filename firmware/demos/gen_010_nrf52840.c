#include "system.h"
#define V_MIN 41

int voltage = 0;

void check_voltage(int v) {
    if (v < V_MIN) {
        GPIO_Write(PIN_P0.11, 1);
        uart_print("UNDERVOLTAGE\n");
    } else {
        GPIO_Write(PIN_P0.11, 0);
        uart_print("V OK\n");
    }
}

int main() {
    while(1) {
        voltage = read_sensor(PIN_P1.02);
        check_voltage(voltage);
    }
    return 0;
}
