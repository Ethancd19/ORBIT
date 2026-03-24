#include "util.h"

#include <stdio.h>
#include <time.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include "platform.h"

#ifndef PRIu64
#define PRIu64 "llu"
#endif

uint64_t now_ns(void) {
#if defined(__linux__) || defined(__APPLE__)
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#else
    return (uint64_t)(platform_cycle_count() * 1000ULL / (PLATFORM_FREQ_HZ / 1000000ULL));
#endif
}

static void sanitize_token(char *str) {
    for (; *str; str++) {
        if (*str == ' ' || *str == ',' || *str == '\t') *str = '_';
    }
}

void make_timestamp_iso_utc(char *out, size_t out_size) {
    if (!out || out_size < 21) {
        if (out && out_size > 0) {
            out[0] = '\0';
        }
        return;
    }
#ifdef _WIN32
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);

    SYSTEMTIME st;
    FileTimeToSystemTime(&ft, &st);

    snprintf(out, out_size, "%04u-%02u-%02uT%02u:%02u:%02uZ",
             st.wYear, st.wMonth, st.wDay,
             st.wHour, st.wMinute, st.wSecond);
#elif defined(__linux__) || defined(__APPLE__)
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    struct tm tm_utc;
    gmtime_r(&ts.tv_sec, &tm_utc);
    snprintf(out, out_size, "%04d-%02d-%02dT%02d:%02d:%02dZ",
             tm_utc.tm_year + 1900, tm_utc.tm_mon + 1, tm_utc.tm_mday,
             tm_utc.tm_hour, tm_utc.tm_min, tm_utc.tm_sec);
#else
        snprintf(out, out_size, "1970-01-01T00:00:00Z");
#endif
}

void make_run_id(char *out, size_t out_size, const char *algorithm, const char *implementation, const char *board, const char *arch) {
    if (!out || out_size < 64) {
        if (out && out_size > 0) {
            out[0] = '\0';
        }
        return;
    }

    char iso[32];
    make_timestamp_iso_utc(iso, sizeof(iso));

    char compact[32];
    snprintf(compact, sizeof(compact), "%.4s%.2s%.2sT%.2s%.2s%.2sZ",
             iso, iso + 5, iso + 8, iso + 11, iso + 14, iso + 17);
    
    char a[64], i[64], b[64], r[64];
    snprintf(a, sizeof(a), "%s", algorithm ? algorithm : "unknown");
    snprintf(i, sizeof(i), "%s", implementation ? implementation : "unknown");
    snprintf(b, sizeof(b), "%s", board ? board : "unknown");
    snprintf(r, sizeof(r), "%s", arch ? arch : "unknown");

    sanitize_token(a);
    sanitize_token(i);
    sanitize_token(b);
    sanitize_token(r);

    snprintf(out, out_size, "%s_%s_%s_%s_%s", compact, a, i, b, r);
}

int parse_u64(const char *str, uint64_t *out) {
    if (!str || !*str || !out) {
        return -1;
    }
    char *endptr = NULL;
    unsigned long long val = strtoull(str, &endptr, 10);
    if (endptr == str || *endptr != '\0' || errno == ERANGE) {
        return -1;
    }
    *out = (uint64_t)val;
    return 1;
}

size_t parse_size_list(const char *csv, size_t *out, size_t out_cap) {
    if (!csv || !out || out_cap == 0) {
        return 0;
    }

    size_t count = 0;
    const char *ptr = csv;
    while (*ptr && count < out_cap) {
        while (*ptr == ' ' || *ptr == '\t' || *ptr == ',') ptr++;
        if (!*ptr) {
            break;
        }
        char *endptr = NULL;
        unsigned long long val = strtoull(ptr, &endptr, 10);
        if (endptr == ptr) {
            break;
        }
        out[count++] = (size_t)val;
        ptr = endptr;
        while (*ptr == ' ' || *ptr == '\t') ptr++;
        if (*ptr == ',') {
            ptr++;
        }
    }
    return count;
}

static uint32_t xorshift32(uint32_t *state) {
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

void fill_deterministic(uint8_t *buf, size_t len, uint32_t seed) {
    uint32_t state = seed;
    for (size_t i = 0; i < len; i++) {
        buf[i] = (uint8_t)(xorshift32(&state) & 0xFF);
    }
}

int bytes_equal(const uint8_t *a, const uint8_t *b, size_t len) {
    for (size_t i = 0; i < len; i++) {
        if (a[i] != b[i]) {
            return 0;
        }
    }
    return 1;
}

void print_hex(const uint8_t *buf, size_t len) {
    for (size_t i = 0; i < len; i++) {
        printf("%02x", buf[i]);
    }
}

void print_csv_header(void) {
    printf(
        "timestamp_iso,run_id,algorithm,implementation,version,board,arch,compiler,compiler_version,cflags,freq_hz,"
        "msg_len,ad_len,key_len,nonce_len,tag_len,iterations,"
        "enc_cycles_total,dec_cycles_total,enc_cycles_per_byte,dec_cycles_per_byte,"
        "enc_time_us_total,dec_time_us_total,enc_time_us_per_op,dec_time_us_per_op,"
        "flash_bytes,ram_bytes,stack_bytes_peak,"
        "energy_uJ_enc_total,energy_uJ_dec_total,energy_uJ_per_byte_enc,energy_uJ_per_byte_dec,avg_power_mW_enc,avg_power_mW_dec,"
        "ok,notes\n"
    );
}

static const char *csv_escape(const char *str) {
    return str ? str : "";
}

void print_csv_row(const csv_row_t *row) {

    printf(
        /* 10 string fields before freq_hz (cflags quoted) */
        "%s,%s,%s,%s,%s,%s,%s,%s,%s,\"%s\",%llu,"
        /* inputs */
        "%zu,%zu,%zu,%zu,%zu,%llu,"
        /* timing */
        "%llu,%llu,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,"
        /* memory */
        "%llu,%llu,%llu,"
        /* energy */
        "%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,"
        /* correctness */
        "%d,\"%s\"\n",

        /* Metadata */
        csv_escape(row->timestamp_iso),
        csv_escape(row->run_id),
        csv_escape(row->algorithm),
        csv_escape(row->implementation),
        csv_escape(row->version),
        csv_escape(row->board),
        csv_escape(row->arch),
        csv_escape(row->compiler),
        csv_escape(row->compiler_version),
        csv_escape(row->cflags),
        (uint64_t)row->freq_hz,

        /* Inputs */
        row->msg_len,
        row->ad_len,
        row->key_len,
        row->nonce_len,
        row->tag_len,
        (uint64_t)row->iterations,

        /* Timing */
        (uint64_t)row->enc_cycles_total,
        (uint64_t)row->dec_cycles_total,
        row->enc_cycles_per_byte,
        row->dec_cycles_per_byte,
        row->enc_time_us_total,
        row->dec_time_us_total,
        row->enc_time_us_per_op,
        row->dec_time_us_per_op,

        /* Memory usage */
        (uint64_t)row->flash_bytes,
        (uint64_t)row->ram_bytes,
        (uint64_t)row->stack_bytes_peak,

        /* Energy usage */
        row->energy_uJ_enc_total,
        row->energy_uJ_dec_total,
        row->energy_uJ_per_byte_enc,
        row->energy_uJ_per_byte_dec,
        row->avg_power_mW_enc,
        row->avg_power_mW_dec,

        /* Correctness */
        row->ok,
        csv_escape(row->notes)
    );

    fflush(stdout);
}
