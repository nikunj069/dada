#include "system.h"
#define CLIP_LIMIT 17

int audio = 0;

void process_audio(int a) {
    if (a > CLIP_LIMIT || a < -CLIP_LIMIT) {
        GPIO_Write(PIN_P0.14, 1); // Clipping indicator
        uart_print("CLIP\n");
        GPIO_Write(PIN_P1.01, 1); // Distorted output
    } else {
        GPIO_Write(PIN_P0.14, 0);
        uart_print("AUDIO OK\n");
        GPIO_Write(PIN_P1.01, a > 0 ? 1 : 0); // Simplified PWM
    }
}

int main() {
    while(1) {
        audio = read_sensor(PIN_P0.12);
        process_audio(audio);
    }
    return 0;
}
