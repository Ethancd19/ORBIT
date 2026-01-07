#ifndef UTIL_H
#define UTIL_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Benchmark output row data
typedef struct {
    /* Metadata */
    const char *timestamp_iso;
    const char *run_id;
    const char *algorithm;
    const char *implementation;
    const char *version;
    const char *board;
    const char *arch;
    const char *compiler;
    const char *compiler_version;
    const char *cflags;
    uint64_t freq_hz;

    /* Inputs */
    size_t msg_len;
    size_t ad_len;
    size_t key_len;
    size_t nonce_len;
    size_t tag_len;
    uint64_t iterations;

    /* Timing */
    uint64_t enc_cycles_total;
    uint64_t dec_cycles_total;
    double enc_cycles_per_byte;
    double dec_cycles_per_byte;
    double enc_time_us_total;
    double dec_time_us_total;

    /* Memory usage */
    uint64_t flash_bytes;
    uint64_t ram_bytes;
    uint64_t stack_bytes_peak;

    /* Energy usage */
    double energy_uJ_enc_total;
    double energy_uJ_dec_total;
    double energy_uJ_per_byte_enc;
    double energy_uJ_per_byte_dec;
    double avg_power_mW_enc;
    double avg_power_mW_dec;

    /* Correctness */
    int ok;
    const char *notes;

} csv_row_t;

/* Timing & Utilities*/
uint64_t now_ns(void);
void fill_deterministic(uint8_t *buf, size_t len, uint32_t seed);
int bytes_equal(const uint8_t *a, const uint8_t *b, size_t len);
void print_hex(const uint8_t *buf, size_t len);
void make_timestamp_iso_utc(char *out, size_t out_size);
void make_run_id(char *out, size_t out_size,
                    const char *algorithm,
                    const char *implementation,
                    const char *board,
                    const char *arch);

/* CSV helpers */
void print_csv_header(void);
void print_csv_row(const csv_row_t *row);

size_t parse_size_list(const char *csv, size_t *out, size_t out_cap);
int parse_u64(const char *str, uint64_t *out);

#ifdef __cplusplus
}
#endif

#endif /* UTIL_H */