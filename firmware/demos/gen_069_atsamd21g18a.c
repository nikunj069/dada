#include "system.h"
#define V_MIN 80

int voltage = 0;

void check_voltage(int v) {
    if (v < V_MIN) {
        GPIO_Write(PIN_PA05, 1);
        uart_print("UNDERVOLTAGE\n");
    } else {
        GPIO_Write(PIN_PA05, 0);
        uart_print("V OK\n");
    }
}

int main() {
    while(1) {
        voltage = read_sensor(PIN_PA04);
        check_voltage(voltage);
    }
    return 0;
}
