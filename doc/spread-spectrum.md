# Spread-spectrum watermarking

## What it is

Spread-spectrum (SS) watermarking borrows from spread-spectrum radio: a small
message is *spread* over a much wider bandwidth (here, many DCT coefficients) so
that each coefficient carries only a tiny, noise-like perturbation. The mark is
invisible per-coefficient and survives because detection **accumulates evidence
over hundreds of coefficients**, where independent distortions average out.

The canonical formulation (Cox et al., 1997) inserts a watermark into the
*perceptually significant* spectral components and detects it by **correlation**
with a key-derived reference sequence. Robustness comes from the spreading gain,
not from any single coefficient being hard to change.

## How this project uses it

Each payload bit `b ∈ {0,1}` becomes an antipodal symbol `s = 2b−1 ∈ {−1,+1}`.
A secret PRNG (derived from the master key, see [key-derivation](key-derivation.md))
assigns every "carrier" — a chosen mid-band DCT coefficient of an 8×8 block — to
a payload bit and gives it a pseudo-random **chip** `χ ∈ {−1,+1}`. Embedding adds

```
coeff += α · mask · χ · s
```

(see [`embed.embed_bits`](../wmlib/embed.py)), where `α` is the strength and
`mask` is a perceptual weight ([perceptual-masking](perceptual-masking.md)).

Detection correlates the received coefficients with the same chips and sums per
bit (a matched filter): `vote_i = Σ χ · coeff''`. The host image acts as
zero-mean noise that cancels over many carriers, so `sign(vote_i)` recovers `s`,
hence the bit. Because only the key-derived chips are needed (not the original),
detection is **blind** ([blind-detection](blind-detection.md)).

Key design points:

- **Carrier plan** in [`spread.build_plan`](../wmlib/spread.py): bits are
  assigned to carriers as evenly as possible, then permuted with the secret PRNG
  — balanced spreading, unpredictable without the key.
- **Two disjoint chip sets / bands** (`MID_BAND` vs `MID_BAND_PUBLIC`) let the
  keyed forensic mark and the public contact mark coexist without interference.
- **Sign-only decision** makes detection invariant to global amplitude scaling
  (brightness/contrast changes, JPEG rescaling of coefficients).

## Trade-offs

- SS gives graceful degradation and amplitude-invariance, but capacity is
  limited: more bits ⇒ fewer carriers per bit ⇒ less spreading gain. We offset
  this with heavy redundancy (tiling) and error correction.
- Pure additive SS suffers host-signal interference; we mitigate it with many
  carriers and zero-mean AC coefficients. Improved-SS (Malvar & Florêncio, 2003)
  partly cancels the host but needs the host estimate at the decoder.

## References

- I. J. Cox, J. Kilian, F. T. Leighton, T. Shamoon, "Secure Spread Spectrum
  Watermarking for Multimedia", *IEEE Trans. Image Processing*, 6(12), 1997.
  https://doi.org/10.1109/83.650120
- H. S. Malvar, D. A. F. Florêncio, "Improved Spread Spectrum: A New Modulation
  Technique for Robust Watermarking", *IEEE Trans. Signal Processing*, 51(4),
  2003. https://doi.org/10.1109/TSP.2003.809385
- I. J. Cox, M. L. Miller, J. A. Bloom, J. Fridrich, T. Kalker, *Digital
  Watermarking and Steganography*, 2nd ed., Morgan Kaufmann, 2008.
- B. Chen, G. W. Wornell, "Quantization Index Modulation: A Class of Provably
  Good Methods for Digital Watermarking and Information Embedding", *IEEE Trans.
  Information Theory*, 47(4), 2001. https://doi.org/10.1109/18.923725 — an
  alternative (host-interference-free) embedding rule we did not use.
