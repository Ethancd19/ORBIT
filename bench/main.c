#include <stdio.h>
#include <string.h>
#include <stdint.h>

#include "util.h"
#include "crypto_aead.h"
#include "api.h"
#include "platform.h"

#define XSTR(x) STR(x)
#define STR(x) #x

#ifndef ALGO_NAME
#define ALGO_NAME "unknown-algo"
#endif
#ifndef BOARD_NAME
#define BOARD_NAME "pico"
#endif
#ifndef VERSION_STR
#define VERSION_STR "unknown-version"
#endif
#ifndef COMPILER_VERSION
#define COMPILER_VERSION "unknown-version"
#endif
#ifndef COMPILER_ID
#define COMPILER_ID "unknown-compiler"
#endif
#ifndef COMPILER_FLAGS
#define COMPILER_FLAGS "unknown-cflags"
#endif
#ifndef TARGET_ARCH
#define TARGET_ARCH "unknown-arch"
#endif

#define NUM_MSG_SIZES        6

static const size_t MSG_SIZES[NUM_MSG_SIZES] = {16, 64, 256, 1024, 4096, 16384};
static const uint32_t BENCH_ITERS[NUM_MSG_SIZES]  = {1000, 1000, 1000, 500, 200, 100};
static const uint32_t WARMUP_ITERS[NUM_MSG_SIZES] = {1000, 1000, 1000, 500, 200, 100};


#define MAX_MSG_LEN          16384
#define MAX_CT_LEN           (MAX_MSG_LEN + 64)

static uint8_t g_m[MAX_MSG_LEN];
static uint8_t g_ad[MAX_MSG_LEN];
static uint8_t g_c[MAX_CT_LEN];
static uint8_t g_m_dec[MAX_MSG_LEN];

#define BENCH_AD_LEN         32

static int correctness_and_tamper(size_t mlen, size_t adlen) {
    uint8_t *m = g_m;
    uint8_t *ad = g_ad;
    uint8_t *c = g_c;
    uint8_t *m_dec = g_m_dec;

    uint8_t key[CRYPTO_KEYBYTES];
    uint8_t nonce[CRYPTO_NPUBBYTES];

    fill_deterministic(key, sizeof(key), 0x12345678);
    fill_deterministic(nonce, sizeof(nonce), 0x87654321);
    fill_deterministic(m, mlen, 0xA5A5A5A5);
    fill_deterministic(ad, adlen, 0x5A5A5A5A);

    unsigned long long clen = 0;
    int enc_rc = crypto_aead_encrypt(c, &clen, m, (unsigned long long)mlen, ad, (unsigned long long)adlen, NULL, nonce, key);
    if (enc_rc != 0) {
        return 0;
    }

    unsigned long long mlen_dec = 0;
    int dec_rc = crypto_aead_decrypt(m_dec, &mlen_dec, NULL, c, clen, ad, (unsigned long long)adlen, nonce, key);

    int ok_roundtrip = (dec_rc == 0) && (mlen_dec == (unsigned long long)mlen) && bytes_equal(m, m_dec, mlen);

    // Tamper with ciphertext
    if (clen > 0) {
        c[0] ^= 0x01; // Flip a bit
    }
    unsigned long long mlen_tamper = 0;
    int dec_tamper_rc = crypto_aead_decrypt(m_dec, &mlen_tamper, NULL, c, clen, ad, (unsigned long long)adlen, nonce, key);

    int ok_tamper = (dec_tamper_rc != 0);

    return ok_roundtrip && ok_tamper;
}

static void bench_one(size_t mlen, size_t adlen, uint32_t iterations, csv_row_t *row) {
    uint8_t *m = g_m;
    uint8_t *ad = g_ad;
    uint8_t *c = g_c;
    uint8_t *m_dec = g_m_dec;

    uint8_t key[CRYPTO_KEYBYTES];
    uint8_t nonce[CRYPTO_NPUBBYTES];

    unsigned long long clen = 0;
    unsigned long long mlen_dec = 0;

    fill_deterministic(key, sizeof(key), 0x12345678);
    fill_deterministic(nonce, sizeof(nonce), 0x87654321);
    fill_deterministic(ad, adlen, 0x5A5A5A5A);
    fill_deterministic(m, mlen, 0xA5A5A5A5);

    (void)crypto_aead_encrypt(c, &clen, m, (unsigned long long)mlen, ad, (unsigned long long)adlen, NULL, nonce, key);

    for (uint32_t i = 0; i < iterations; i++) {
        fill_deterministic(m, mlen, (uint32_t)(0xA5A5A5A5 + i));
        (void)crypto_aead_encrypt(c, &clen, m, (unsigned long long)mlen, ad, (unsigned long long)adlen, NULL, nonce, key);
    }

    // Benchmark encryption
    platform_trigger_high();
    uint64_t start_enc_cycles = platform_cycle_count();

    for (uint32_t i = 0; i < iterations; i++) {
        fill_deterministic(m, mlen, (uint32_t)(0xA5A5A5A5 + i));
        int rc = crypto_aead_encrypt(c, &clen, m, (unsigned long long)mlen, ad, (unsigned long long)adlen, NULL, nonce, key);
        if (rc != 0) {
            platform_trigger_low();
            row->ok = 0;
            row->notes = "Encryption failed during benchmarking";
            return;
        }
    }

    uint64_t end_enc_cycles = platform_cycle_count();
    platform_trigger_low();

    for (uint32_t i = 0; i < iterations; i++) {
        (void)crypto_aead_decrypt(m_dec, &mlen_dec, NULL, c, clen, ad, (unsigned long long)adlen, nonce, key);
    }

    // Benchmark decryption
    platform_trigger_high();
    uint64_t start_dec_cycles = platform_cycle_count();

    for (uint64_t i = 0; i < iterations; i++) {
        int rc = crypto_aead_decrypt(m_dec, &mlen_dec, NULL, c, clen, ad, (unsigned long long)adlen, nonce, key);
        if (rc != 0) {
            platform_trigger_low();
            row->ok = 0;
            row->notes = "Decryption failed during benchmarking";
            return;
        }
    }
    uint64_t end_dec_cycles = platform_cycle_count();
    platform_trigger_low();

    uint64_t enc_cycles_total = end_enc_cycles - start_enc_cycles;
    uint64_t dec_cycles_total = end_dec_cycles - start_dec_cycles;

    // Correctness check
    fill_deterministic(m, mlen, (uint32_t)(0xA5A5A5A5 + iterations - 1));
    int ok_correctness = (mlen_dec == (unsigned long long)mlen) && bytes_equal(m, m_dec, mlen);


    row->msg_len = mlen;
    row->ad_len = adlen;
    row->key_len = CRYPTO_KEYBYTES;
    row->nonce_len = CRYPTO_NPUBBYTES;
    row->tag_len = CRYPTO_ABYTES;
    row->iterations = iterations;
    row->freq_hz = platform_freq_hz();

    row->enc_cycles_total = enc_cycles_total;
    row->dec_cycles_total = dec_cycles_total;
    row->enc_cycles_per_byte = (mlen > 0) ? (double)enc_cycles_total / (double)(mlen * iterations) : 0.0;
    row->dec_cycles_per_byte = (mlen > 0) ? (double)dec_cycles_total / (double)(mlen * iterations) : 0.0;

    row->enc_time_us_total  = (double)enc_cycles_total / ((double)platform_freq_hz() / 1e6);
    row->dec_time_us_total  = (double)dec_cycles_total / ((double)platform_freq_hz() / 1e6);
    row->enc_time_us_per_op = row->enc_time_us_total / iterations;
    row->dec_time_us_per_op = row->dec_time_us_total / iterations;

    row->ok = ok_correctness ? 1 : 0;
    row->notes = row->notes ? row->notes : "";
}

int main(void) {
    // size_t *msg_lens = NULL;
    // size_t msg_count = 0;
    // size_t *ad_lens = NULL;
    // size_t ad_count = 0;
    // uint64_t iter_small = DEFAULT_ITERATIONS_SMALL;
    // uint64_t iter_large = DEFAULT_ITERATIONS_LARGE;

    // for (int i = 1; i < argc; i++) {
    //     const char *arg = argv[i];

    //     if (streq(arg, "-l")) {
    //         const char *v = need_value(&i, argc, argv, "-l");
    //         static size_t msg_lens_buf[100];
    //         msg_count = parse_size_list(v, msg_lens, 100);
    //         if (msg_count == 0) { fprintf(stderr, "No valid message lengths provided.\n"); return 1; }

    //     } else if (streq(arg, "-a")) {
    //         const char *v = need_value(&i, argc, argv, "-a");
    //         static size_t ad_lens_buf[100];
    //         ad_count = parse_size_list(v, ad_lens, 100);
    //         if (ad_count == 0) { fprintf(stderr, "No valid AD lengths provided.\n"); return 1; }

    //     } else if (streq(arg, "-i")) {
    //         const char *v = need_value(&i, argc, argv, "-i");
    //         if (!parse_u64(v, &iter_small)) { fprintf(stderr, "Invalid -i value.\n"); return 1; }

    //     } else if (streq(arg, "-I")) {
    //         const char *v = need_value(&i, argc, argv, "-I");
    //         if (!parse_u64(v, &iter_large)) { fprintf(stderr, "Invalid -I value.\n"); return 1; }

    //     } else if (streq(arg, "-h") || streq(arg, "--help")) {
    //         print_help(argv[0]);
    //         return 0;

    //     } else {
    //         fprintf(stderr, "Unknown option: %s\n", arg);
    //         print_help(argv[0]);
    //         return 1;
    //     }
    // }

    // if (!msg_lens) {
    //     msg_count = 4;
    //     msg_lens = malloc(sizeof(size_t) * msg_count);
    //     size_t d[] = {16, 64, 256, 1024};
    //     memcpy(msg_lens, d, sizeof(d));
    // }
    // if (!ad_lens) {
    //     ad_count = 2;
    //     ad_lens = malloc(sizeof(size_t) * ad_count);
    //     size_t d[] = {0, 32};
    //     memcpy(ad_lens, d, sizeof(d));
    // }
    platform_init();

    while (!stdio_usb_connected()) {
        sleep_ms(100);
    }
    sleep_ms(500);  

    print_csv_header();

    for (size_t s = 0; s < NUM_MSG_SIZES; s++) {
        size_t mlen = MSG_SIZES[s];
        size_t adlen = BENCH_AD_LEN;
        uint32_t iters = BENCH_ITERS[s];

        csv_row_t row = {0};
        char ts[32];
        char rid[256];

        make_timestamp_iso_utc(ts, sizeof(ts));
        make_run_id(rid, sizeof(rid), XSTR(ALGO_NAME), BOARD_NAME, BOARD_NAME, TARGET_ARCH);

        row.timestamp_iso = ts;
        row.run_id = rid;
        row.algorithm = XSTR(ALGO_NAME);
        row.implementation = "ref";
        row.version = VERSION_STR;
        row.board = BOARD_NAME;
        row.cflags = COMPILER_FLAGS;
        row.arch = TARGET_ARCH;
        row.compiler = COMPILER_ID;
        row.compiler_version = COMPILER_VERSION;

        if (!correctness_and_tamper(mlen, adlen)) {
            row.ok = 0;
            row.notes = "KAT failure or tamper check failed";
            print_csv_row(&row);
            continue;
        }

        bench_one(mlen, adlen, iters, &row);
        print_csv_row(&row);
    }

    printf("ECLIPSE benchmark completed.\n");
    fflush(stdout);

    while (1) {}

    return 0;
}