#ifndef PLATFORM_H
#define PLATFORM_H

#include <stdint.h>
#include "pico/stdlib.h"
#include "hardware/gpio.h"

#define PLATFORM_FREQ_HZ 125000000UL
#define TRIGGER_PIN 15

static inline void platform_init(void) {
    stdio_init_all();
    gpio_init(TRIGGER_PIN);
    gpio_set_dir(TRIGGER_PIN, GPIO_OUT);
    gpio_put(TRIGGER_PIN, 0);
}

static inline uint64_t platform_cycle_count(void) {
    return time_us_64() * (PLATFORM_FREQ_HZ / 1000000UL);
}

static inline void platform_trigger_high(void) {
    gpio_put(TRIGGER_PIN, 1);
}

static inline void platform_trigger_low(void) {
    gpio_put(TRIGGER_PIN, 0);
}

static inline uint32_t platform_freq_hz(void) {
    return PLATFORM_FREQ_HZ;
}

#endif // PLATFORM_H