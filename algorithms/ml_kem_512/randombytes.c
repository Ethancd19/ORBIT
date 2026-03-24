#include "randombytes.h"
#include <stdint.h>
#include <stddef.h>

/* Deterministic PRNG for benchmarking only - NOT cryptographically secure */
static uint32_t rng_state = 0xDEADBEEF;

static uint32_t xorshift32(void) {
    rng_state ^= rng_state << 13;
    rng_state ^= rng_state >> 17;
    rng_state ^= rng_state << 5;
    return rng_state;
}

void randombytes(uint8_t *out, size_t outlen) {
    for (size_t i = 0; i < outlen; i++) {
        if (i % 4 == 0) xorshift32();
        out[i] = (uint8_t)(rng_state >> (8 * (i % 4)));
    }
}