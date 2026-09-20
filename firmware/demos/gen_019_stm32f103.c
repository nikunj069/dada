#include "system.h"
#define CLIP_LIMIT 72

int audio = 0;

void process_audio(int a) {
    if (a > CLIP_LIMIT || a < -CLIP_LIMIT) {
        GPIO_Write(PIN_PA1, 1); // Clipping indicator
        uart_print("CLIP\n");
        GPIO_Write(PIN_PA3, 1); // Distorted output
    } else {
        GPIO_Write(PIN_PA1, 0);
        uart_print("AUDIO OK\n");
        GPIO_Write(PIN_PA3, a > 0 ? 1 : 0); // Simplified PWM
    }
}

int main() {
    while(1) {
        audio = read_sensor(PIN_PB0);
        process_audio(audio);
    }
    return 0;
}
