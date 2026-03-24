#include "api.h"
#include "crypto_aead.h"
#include "aes.h"
#include "modes.h"
#include <string.h>
#include <stdint.h>

int crypto_aead_encrypt(
    unsigned char *c, unsigned long long *clen,
    const unsigned char *m, unsigned long long mlen,
    const unsigned char *ad, unsigned long long adlen,
    const unsigned char *nsec,
    const unsigned char *npub,
    const unsigned char *k)
{
    (void)nsec;

    cf_aes_context aes;
    cf_aes_init(&aes, k, CRYPTO_KEYBYTES);

    uint8_t tag[CRYPTO_ABYTES];

    cf_gcm_encrypt(&cf_aes, &aes,
                   m, (size_t)mlen,
                   ad, (size_t)adlen,
                   npub, (size_t)CRYPTO_NPUBBYTES,
                   c,
                   tag, (size_t)CRYPTO_ABYTES);

    memcpy(c + mlen, tag, CRYPTO_ABYTES);
    *clen = mlen + CRYPTO_ABYTES;
    return 0;
}

int crypto_aead_decrypt(
    unsigned char *m, unsigned long long *mlen,
    unsigned char *nsec,
    const unsigned char *c, unsigned long long clen,
    const unsigned char *ad, unsigned long long adlen,
    const unsigned char *npub,
    const unsigned char *k)
{
    (void)nsec;

    if (clen < CRYPTO_ABYTES) return -1;

    size_t msglen = (size_t)(clen - CRYPTO_ABYTES);
    const uint8_t *tag = c + msglen;

    cf_aes_context aes;
    cf_aes_init(&aes, k, CRYPTO_KEYBYTES);

    int rc = cf_gcm_decrypt(&cf_aes, &aes,
                            c, msglen,
                            ad, (size_t)adlen,
                            npub, (size_t)CRYPTO_NPUBBYTES,
                            tag, (size_t)CRYPTO_ABYTES,
                            m);

    if (rc != 0) return -1;

    *mlen = (unsigned long long)msglen;
    return 0;
}