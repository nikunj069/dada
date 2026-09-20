#include "system.h"
#define CLIP_LIMIT 42

int audio = 0;

void process_audio(int a) {
    if (a > CLIP_LIMIT || a < -CLIP_LIMIT) {
        GPIO_Write(PIN_PA05, 1); // Clipping indicator
        uart_print("CLIP\n");
        GPIO_Write(PIN_PB09, 1); // Distorted output
    } else {
        GPIO_Write(PIN_PA05, 0);
        uart_print("AUDIO OK\n");
        GPIO_Write(PIN_PB09, a > 0 ? 1 : 0); // Simplified PWM
    }
}

int main() {
    while(1) {
        audio = read_sensor(PIN_PB08);
        process_audio(audio);
    }
    return 0;
}
