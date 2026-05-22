# Payload format and the dual channel

## What it is

The "payload" is the message actually embedded — not the raw id, but a framed,
protected, fixed-length **codeword**. Framing (magic/version/length), integrity
or authentication, and forward error correction are layered so the detector can
tell a valid mark from noise and recover it under attack. Watermarking schemes
typically use a **fixed-length codeword** so the embedder can repeat one
constant-size block across the medium — which is what makes cropping survivable
(a crop still contains whole copies).

## How this project uses it

Two independent payloads live on disjoint DCT bands (see
[dct-domain](dct-domain.md)) so they coexist without interference.

### Forensic payload — [`payload.py`](../wmlib/payload.py)

```
recipient id (≤32 B UTF-8)
  → [len(1) | id | zero-pad to 32]                       (33 B plaintext block)
  → AES-256-GCM(enc_key, nonce)                           (+12 B nonce, +16 B tag)
  → frame: [version(1) | nonce(12) | ciphertext(49)]      (62 B)
  → Reed–Solomon(+32 parity)                              (94 B = 752 bits)
```

Decode reverses it: RS-correct → check version → AES-GCM verify. Authenticated,
so a wrong key or any tampering is rejected, never returned as a forged id.

### Public contact payload — [`payload_public.py`](../wmlib/payload_public.py)

```
contact (≤48 B UTF-8)
  → frame: [magic "WC"(2) | version(1) | len(1) | contact | pad to 48 | CRC32(4)]  (56 B)
  → Reed–Solomon(+32 parity)                                                       (88 B = 704 bits)
```

No encryption (public by design); the **CRC32 + magic** only guard against
decoding noise into a bogus string when no mark is present. This is *integrity*,
not *authenticity* — anyone can read, strip or rewrite it. It is the invisible
twin of the visible "if found, contact …" notice.

The fixed lengths (94 / 88 bytes) are repeated across the image by the carrier
plan; a `TILE×TILE` tile holds a whole codeword, giving crop redundancy on top of
the RS error correction.

## Trade-offs

- Capacity is tight: GCM overhead (28 B) + RS parity (32 B) dominate the 94-byte
  forensic codeword, capping the id at 32 bytes. The fixed format trades
  flexibility for robustness and a simple, repeatable embed.
- A magic+version header costs a few bytes but enables clean rejection and
  future format evolution.

## References

- I. J. Cox, M. L. Miller, J. A. Bloom, J. Fridrich, T. Kalker, *Digital
  Watermarking and Steganography*, 2nd ed., Morgan Kaufmann, 2008 (payload
  coding, error correction and capacity).
- See [reed-solomon.md](reed-solomon.md) and
  [authenticated-encryption.md](authenticated-encryption.md) for the protection
  layers; W. W. Peterson, D. T. Brown, "Cyclic Codes for Error Detection",
  *Proc. IRE*, 49(1), 1961, https://doi.org/10.1109/JRPROC.1961.287814 (CRC).
