#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#define F_OK 0
#define access _access
#else
#include <unistd.h>
#endif
#include <stdint.h>

#include "util.h"
#include "crypto_aead.h"
#include "api.h"

static int streq(const char *a, const char *b) {
    return strcmp(a, b) == 0;
}

static const char *need_value(int *i, int argc, char **argv, const char *flag) {
    if (*i + 1 >= argc) {
        fprintf(stderr, "Missing value for %s\n", flag);
        exit(1);
    }
    (*i)++;
    return argv[*i];
}

#define XSTR(x) STR(x)
#define STR(x) #x

#ifndef ALGO_NAME
#define ALGO_NAME "unknown-algo"
#endif
#ifndef IMPL_NAME
#define IMPL_NAME "unknown-impl"
#endif
#ifndef BOARD_NAME
#define BOARD_NAME "pc"
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

#define DEFAULT_ITERATIONS_SMALL 20000
#define DEFAULT_ITERATIONS_LARGE 2000

static int correctness_and_tamper(size_t mlen, size_t adlen) {
    uint8_t *m = (uint8_t *)malloc(mlen);
    uint8_t *ad = (uint8_t *)malloc(adlen);
    uint8_t *c = (uint8_t *)malloc(mlen + CRYPTO_ABYTES);
    uint8_t *m_dec = (uint8_t *)malloc(mlen);

    if (!m || !ad || !c || !m_dec) {
        fprintf(stderr, "Memory allocation failed\n");
        return 0;
    }

    uint8_t key[CRYPTO_KEYBYTES];
    uint8_t nonce[CRYPTO_NPUBBYTES];

    fill_deterministic(key, sizeof(key), 0x12345678);
    fill_deterministic(nonce, sizeof(nonce), 0x87654321);
    fill_deterministic(m, mlen, 0xA5A5A5A5);
    fill_deterministic(ad, adlen, 0x5A5A5A5A);

    unsigned long long clen = 0;
    int enc_rc = crypto_aead_encrypt(c, &clen, m, (unsigned long long)mlen, ad, (unsigned long long)adlen, NULL, nonce, key);
    if (enc_rc != 0) {
        fprintf(stderr, "Encryption failed\n");
        free(m);
        free(ad);
        free(c);
        free(m_dec);
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

    free(m);
    free(ad);
    free(c);
    free(m_dec);
    return ok_roundtrip && ok_tamper;
}

static void bench_one(size_t mlen, size_t adlen, uint64_t iterations, csv_row_t *row) {
    uint8_t *m = (uint8_t *)malloc(mlen);
    uint8_t *ad = (uint8_t *)malloc(adlen);
    uint8_t *c = (uint8_t *)malloc(mlen + CRYPTO_ABYTES);
    uint8_t *m_dec = (uint8_t *)malloc(mlen);

    uint8_t key[CRYPTO_KEYBYTES];
    uint8_t nonce[CRYPTO_NPUBBYTES];

    unsigned long long clen = 0;
    unsigned long long mlen_dec = 0;

    if (!m || !ad || !c || !m_dec) {
        row->ok = 0;
        row->notes = "Memory allocation failed";
        return;
    }

    fill_deterministic(key, sizeof(key), 0x12345678);
    fill_deterministic(nonce, sizeof(nonce), 0x87654321);
    fill_deterministic(ad, adlen, 0x5A5A5A5A);

    fill_deterministic(m, mlen, 0xA5A5A5A5);
    (void)crypto_aead_encrypt(c, &clen, m, (unsigned long long)mlen, ad, (unsigned long long)adlen, NULL, nonce, key);
    (void)crypto_aead_decrypt(m_dec, &mlen_dec, NULL, c, clen, ad, (unsigned long long)adlen, nonce, key);

    // Benchmark encryption
    uint64_t start_enc = now_ns();
    for (uint64_t i = 0; i < iterations; i++) {
        fill_deterministic(m, mlen, (uint32_t)(0xA5A5A5A5 + i));
        int rc = crypto_aead_encrypt(c, &clen, m, (unsigned long long)mlen, ad, (unsigned long long)adlen, NULL, nonce, key);
        if (rc != 0) {
            row->ok = 0;
            row->notes = "Encryption failed during benchmarking";
            free(m);
            free(ad);
            free(c);
            free(m_dec);
            return;
        }
    }
    uint64_t end_enc = now_ns();

    // Benchmark decryption
    uint64_t start_dec = now_ns();
    for (uint64_t i = 0; i < iterations; i++) {
        int rc = crypto_aead_decrypt(m_dec, &mlen_dec, NULL, c, clen, ad, (unsigned long long)adlen, nonce, key);
        if (rc != 0) {
            row->ok = 0;
            row->notes = "Decryption failed during benchmarking";
            free(m);
            free(ad);
            free(c);
            free(m_dec);
            return;
        }
    }
    uint64_t end_dec = now_ns();

    // Correctness check
    fill_deterministic(m, mlen, (uint32_t)0xA5A5A5A5 + (iterations ? iterations - 1 : 0));
    int ok_correctness = (mlen_dec == (unsigned long long)mlen) && bytes_equal(m, m_dec, mlen);


    row->enc_time_us_total = (double)(end_enc - start_enc) / 1000.0;
    row->dec_time_us_total = (double)(end_dec - start_dec) / 1000.0;
    row->iterations = iterations;
    row->enc_time_us_per_op = (iterations > 0) ? row->enc_time_us_total / (double)iterations : 0.0;
    row->dec_time_us_per_op = (iterations > 0) ? row->dec_time_us_total / (double)iterations : 0.0;
    
    row->msg_len = mlen;
    row->ad_len = adlen;
    row->key_len = CRYPTO_KEYBYTES;
    row->nonce_len = CRYPTO_NPUBBYTES;
    row->tag_len = CRYPTO_ABYTES;

    row->ok = ok_correctness ? 1 : 0;
    if(!row->notes) {
        row->notes = "";
    }
    free(m);
    free(ad);
    free(c);
    free(m_dec);
}

void print_help(const char *progname) {
    fprintf(stderr, "Usage: %s [options]\n", progname);
    fprintf(stderr, "Options:\n");
    fprintf(stderr, "  -l <list>   Comma-separated list of message lengths (e.g., \"16,64,1024\")\n");
    fprintf(stderr, "  -a <list>   Comma-separated list of AD lengths (e.g., \"0,32\")\n");
    fprintf(stderr, "  -i <num>    Iterations for small messages (default: %d)\n", DEFAULT_ITERATIONS_SMALL);
    fprintf(stderr, "  -I <num>    Iterations for large messages (default: %d)\n", DEFAULT_ITERATIONS_LARGE);
    fprintf(stderr, "  -h          Show this help message\n");
}

int main(int argc, char **argv) {
    size_t *msg_lens = NULL;
    size_t msg_count = 0;
    size_t *ad_lens = NULL;
    size_t ad_count = 0;
    uint64_t iter_small = DEFAULT_ITERATIONS_SMALL;
    uint64_t iter_large = DEFAULT_ITERATIONS_LARGE;

    for (int i = 1; i < argc; i++) {
        const char *arg = argv[i];

        if (streq(arg, "-l")) {
            const char *v = need_value(&i, argc, argv, "-l");
            msg_lens = malloc(sizeof(size_t) * 100);
            msg_count = parse_size_list(v, msg_lens, 100);
            if (msg_count == 0) { fprintf(stderr, "No valid message lengths provided.\n"); return 1; }

        } else if (streq(arg, "-a")) {
            const char *v = need_value(&i, argc, argv, "-a");
            ad_lens = malloc(sizeof(size_t) * 100);
            ad_count = parse_size_list(v, ad_lens, 100);
            if (ad_count == 0) { fprintf(stderr, "No valid AD lengths provided.\n"); return 1; }

        } else if (streq(arg, "-i")) {
            const char *v = need_value(&i, argc, argv, "-i");
            if (!parse_u64(v, &iter_small)) { fprintf(stderr, "Invalid -i value.\n"); return 1; }

        } else if (streq(arg, "-I")) {
            const char *v = need_value(&i, argc, argv, "-I");
            if (!parse_u64(v, &iter_large)) { fprintf(stderr, "Invalid -I value.\n"); return 1; }

        } else if (streq(arg, "-h") || streq(arg, "--help")) {
            print_help(argv[0]);
            return 0;

        } else {
            fprintf(stderr, "Unknown option: %s\n", arg);
            print_help(argv[0]);
            return 1;
        }
    }

    if (!msg_lens) {
        msg_count = 4;
        msg_lens = malloc(sizeof(size_t) * msg_count);
        size_t d[] = {16, 64, 256, 1024};
        memcpy(msg_lens, d, sizeof(d));
    }
    if (!ad_lens) {
        ad_count = 2;
        ad_lens = malloc(sizeof(size_t) * ad_count);
        size_t d[] = {0, 32};
        memcpy(ad_lens, d, sizeof(d));
    }

    print_csv_header();

    for (size_t i = 0; i < msg_count; i++) {
        for (size_t j = 0; j < ad_count; j++) {
            size_t mlen = msg_lens[i];
            size_t adlen = ad_lens[j];
            uint64_t iters = (mlen <= 256) ? iter_small : iter_large;

            csv_row_t row = {0};
            char ts[32];
            char rid[256];
            make_timestamp_iso_utc(ts, sizeof(ts));
            make_run_id(rid, sizeof(rid), XSTR(ALGO_NAME), XSTR(IMPL_NAME), BOARD_NAME, TARGET_ARCH);

            row.timestamp_iso = ts;
            row.run_id = rid;
            row.algorithm = XSTR(ALGO_NAME);
            row.implementation = XSTR(IMPL_NAME);
            row.version = VERSION_STR;
            row.board = BOARD_NAME;
            row.cflags = COMPILER_FLAGS;
            row.arch = TARGET_ARCH;
            row.compiler = COMPILER_ID;
            row.compiler_version = COMPILER_VERSION;

            if (!correctness_and_tamper(mlen, adlen)) {
                row.ok = 0;
                row.notes = "Sanity Check Failed";
                print_csv_row(&row);
                continue;
            }

            // Run Benchmark
            bench_one(mlen, adlen, iters, &row);
            print_csv_row(&row);
        }
    }

    free(msg_lens);
    free(ad_lens);
    return 0;
}