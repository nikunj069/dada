#include "system.h"
#define CLIP_LIMIT 15

int audio = 0;

void process_audio(int a) {
    if (a > CLIP_LIMIT || a < -CLIP_LIMIT) {
        GPIO_Write(PIN_PB08, 1); // Clipping indicator
        uart_print("CLIP\n");
        GPIO_Write(PIN_PA02, 1); // Distorted output
    } else {
        GPIO_Write(PIN_PB08, 0);
        uart_print("AUDIO OK\n");
        GPIO_Write(PIN_PA02, a > 0 ? 1 : 0); // Simplified PWM
    }
}

int main() {
    while(1) {
        audio = read_sensor(PIN_PA04);
        process_audio(audio);
    }
    return 0;
}
