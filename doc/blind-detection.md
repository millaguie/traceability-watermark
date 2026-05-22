# Blind detection

## What it is

A watermark detector is **blind** (a.k.a. *oblivious*) if it recovers the mark
**without the original, unmarked content** — using only the received media and
the secret key. The opposite (informed/non-blind) detection needs the original
as a reference. Blind detection is essential for traceability: when a leaked
copy surfaces, you rarely have the exact original to compare against.

For spread-spectrum marks, blind detection is a **correlation / matched filter**:
correlate the received signal with the key-derived chip sequence; the sign of
the correlation gives the bit, and its magnitude is a confidence.

## How this project uses it

[`extract.py`](../wmlib/extract.py):

1. **Block-DCT of the received image** (`block_coeffs`), optionally shifted by a
   sub-block pixel origin for synchronization.
2. **Per-bit votes.** For each carrier, multiply the coefficient by its chip and
   accumulate into the bit it carries: `vote_i = Σ χ · coeff`. Positive ⇒ bit 1
   (`votes_to_bits`).
3. **Confidence.** The vote energy `Σ vote_i²` is high only when the detector is
   correctly synchronized, so it doubles as a sync score (`best_offset_votes`).

### The phase-bin pooling optimization

A naive detector recomputes the per-bit sum for every candidate tile offset.
Because the embedding is **periodic with period `TILE` blocks**, every block at
the same position *modulo* `TILE` (a "phase bin") shares the same chip/bit for a
given offset. So we pool coefficients into a `TILE×TILE` grid of phase bins
**once** (`phase_sums`, two small matrix multiplies), and each of the `TILE²`
tile offsets is then a tiny operation on a `TILE×TILE×n_slots` array, independent
of image size. This made a clean extraction drop from ~12 s to ~0.02 s.

Authentication makes detection sound: a recovered bitstream is only accepted if
Reed–Solomon decodes and AES-GCM verifies ([authenticated-encryption](authenticated-encryption.md)),
so the detector never returns a false or coincidental id.

## Trade-offs

- Blind detection has lower capacity/robustness than informed detection (the
  host is unknown noise), traded for the practical ability to detect anywhere.
- Hard-decision bits feed the byte-level Reed–Solomon decoder; a soft-decision
  (LLR) front end into a soft decoder could squeeze out more margin but adds
  complexity.

## References

- I. J. Cox, M. L. Miller, A. L. McKellips, "Watermarking as Communications with
  Side Information", *Proceedings of the IEEE*, 87(7), 1999.
  https://doi.org/10.1109/5.771068
- T. Kalker, J.-P. Linnartz, M. van Dijk, "Watermark Estimation through Detector
  Analysis", *Proc. IEEE ICIP*, 1998. https://doi.org/10.1109/ICIP.1998.723516
- I. J. Cox, J. Kilian, F. T. Leighton, T. Shamoon, "Secure Spread Spectrum
  Watermarking for Multimedia", *IEEE Trans. Image Processing*, 6(12), 1997.
  https://doi.org/10.1109/83.650120
