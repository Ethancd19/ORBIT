#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#include "util.h"
#include "crypto_aead.h"
#include "api.h"

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

int main(void) {
    /* Config */
    const char *algorithm = "ascon-aead128";
    const char *implementation = "reference";
    const char *version = "TEST";
    const char *board = "pc";
    const char *arch = "x86_64";
    const char *compiler = "gcc";
    const char *compiler_version = "TEST";
    const char *cflags = "TEST";

    const size_t msg_lens[] = {16, 64, 256, 1024, 10 * 1024};
    const size_t ad_lens[] = {0, 32};

    const uint64_t iterations_small = 20000;
    const uint64_t iterations_large = 2000;

    print_csv_header();

    for (size_t i = 0; i < sizeof(msg_lens) / sizeof(msg_lens[0]); i++) {
        for (size_t j = 0; j < sizeof(ad_lens) / sizeof(ad_lens[0]); j++) {
            size_t mlen = msg_lens[i];
            size_t adlen = ad_lens[j];
            uint64_t iterations = (mlen <= 256) ? iterations_small : iterations_large;
            char ts_iso[32];
            char run_id[192];
            make_timestamp_iso_utc(ts_iso, sizeof(ts_iso));
            make_run_id(run_id, sizeof(run_id), algorithm, implementation, board, arch);
            
            csv_row_t row = {0};
            row.timestamp_iso = ts_iso;
            row.run_id = run_id;
            row.algorithm = algorithm;
            row.implementation = implementation;
            row.version = version;
            row.board = board;
            row.arch = arch;
            row.compiler = compiler;
            row.compiler_version = compiler_version;
            row.cflags = cflags;
            row.freq_hz = 0; // Example frequency
            
            row.enc_cycles_total = 0;
            row.dec_cycles_total = 0;
            row.enc_cycles_per_byte = 0.0;
            row.dec_cycles_per_byte = 0.0;

            row.flash_bytes = 0;
            row.ram_bytes = 0;
            row.stack_bytes_peak = 0;

            row.energy_uJ_enc_total = 0.0;
            row.energy_uJ_dec_total = 0.0;
            row.energy_uJ_per_byte_enc = 0.0;
            row.energy_uJ_per_byte_dec = 0.0;
            row.avg_power_mW_enc = 0.0;
            row.avg_power_mW_dec = 0.0;

            // Basic Correctness and tamper test
            int ok_tamper = correctness_and_tamper(mlen, adlen);
            if (!ok_tamper) {
                row.msg_len = mlen;
                row.ad_len = adlen;
                row.key_len = CRYPTO_KEYBYTES;
                row.nonce_len = CRYPTO_NPUBBYTES;
                row.tag_len = CRYPTO_ABYTES;
                row.iterations = 0;
                row.ok = 0;
                row.notes = "Tamper detection failed";
                print_csv_row(&row);
                continue;
            }

            bench_one(mlen, adlen, iterations, &row);
            print_csv_row(&row);
        }
    }

    return 0;
}