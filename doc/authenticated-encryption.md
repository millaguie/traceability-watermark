# Authenticated encryption (AES-256-GCM)

## What it is

**Authenticated Encryption with Associated Data (AEAD)** provides three
properties at once: *confidentiality* (the plaintext is hidden), *integrity*
(tampering is detected), and *authenticity* (only a holder of the key could have
produced the ciphertext). **AES-GCM** is the most widely deployed AEAD: AES in
counter mode for encryption, combined with a GHASH-based authentication tag over
the Galois field GF(2^128). Decryption recomputes the tag and **fails closed**
if it does not match.

A critical operational rule: GCM is catastrophic under **nonce reuse** with the
same key — never encrypt two messages with the same (key, nonce) pair.

## How this project uses it

[`payload.py`](../wmlib/payload.py) protects the recipient id with AES-256-GCM
(`cryptography`'s `AESGCM`):

- The id (length-prefixed, padded to a fixed block) is encrypted with the
  `enc` subkey ([key-derivation](key-derivation.md)) and a **fresh random 12-byte
  nonce** per embed; the nonce travels in the payload.
- The 16-byte GCM tag authenticates the result.

This gives the forensic mark its two security guarantees:

- **Confidentiality** — without the key, an attacker cannot read which recipient
  a copy was issued to (the bits are also key-scrambled by the spreading, but
  GCM is the real confidentiality boundary).
- **Unforgeability** — an attacker cannot fabricate or alter a valid id; on
  extraction, any tampering (or a wrong key) makes the tag verification fail, so
  `decode_payload` raises and the tool reports "no valid mark" instead of
  returning a forged identifier. This is what lets the tool *never* output a
  coincidental or attacker-chosen id.

The **public contact** mark is deliberately *not* encrypted — it is meant to be
world-readable — and uses a CRC32 only for integrity, not authenticity
([payload-format](payload-format.md)).

## Trade-offs

- AEAD overhead (12-byte nonce + 16-byte tag = 28 bytes) is significant given
  the tiny watermark capacity, but buys real confidentiality + unforgeability.
  An HMAC-only design would be lighter but wouldn't hide the id.
- Random-nonce GCM is safe here because each embed is independent; we never
  re-encrypt the same payload under a fixed nonce.

## References

- NIST, *FIPS 197: Advanced Encryption Standard (AES)*, 2001 (updated 2023).
  https://csrc.nist.gov/pubs/fips/197/final
- D. McGrew, J. Viega, "The Galois/Counter Mode of Operation (GCM)", 2004.
- M. Dworkin, *NIST SP 800-38D: Recommendation for Block Cipher Modes of
  Operation: Galois/Counter Mode (GCM) and GMAC*, 2007.
  https://csrc.nist.gov/pubs/sp/800/38/d/final
- P. Rogaway, "Authenticated-Encryption with Associated-Data", *ACM CCS*, 2002.
  https://doi.org/10.1145/586110.586125
