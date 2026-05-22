# Geometric synchronization (resync)

## What it is

Block-based watermarks assume the detector reads the **same grid** the embedder
wrote. Any geometric change — cropping, translation, rotation, scaling — shifts
or warps that grid and **de-synchronizes** the detector: correlation collapses
even though the mark is still present. Resynchronization is the problem of
recovering the embedding grid before detection. It is widely regarded as the
hardest part of robust watermarking (the "RST" — rotation/scale/translation —
problem).

Two broad families:

- **Search / brute force:** try candidate corrections and keep the one that
  detects. Works well when distortions are *bounded*.
- **Invariant domains / templates:** embed in a domain invariant to the
  transform (e.g. Fourier–Mellin / log-polar for rotation+scale), or embed a
  known template/pilot to estimate the distortion. More general, more complex.

## How this project uses it

The threat model bounds distortions (crop ≤10%, scale ±20%, rotation ±2°), so we
use a **bounded search** ([`api._search_decode`](../wmlib/api.py)):

1. **Tile offset** (translation at block granularity): the carrier plan is
   periodic with `TILE` blocks, so trying the `TILE²` tile origins covers any
   whole-block translation; the periodic signal is self-clocking. Done cheaply
   via phase-bin pooling ([blind-detection](blind-detection.md)).
2. **Pixel origin** (sub-block translation): a crop of, say, 51 px shifts the
   8×8 grid by 3 px, which whole-block offsets cannot fix. So we also search the
   8×8 sub-block origins (`block_coeffs(origin=(sy,sx))`). This must stay a
   step-1 search — coarser steps miss real crop offsets.
3. **Rotation / scale** (`imageops.resample`): for each candidate (angle, scale)
   correction we de-rotate/de-scale, then run the offset search. The grid is
   small and bounded.

Performance tiering (`SearchSpec`): because detection always runs on the
canonical (≤1024 px) image after [scale normalization](scale-invariance.md), the
geometric search is cheap, so the **default already searches a small
scale/rotation grid** (covering ~±20% scale, ~12% crop and ±2° rotation).
`--full` widens it to a dense grid for awkward distortions. A successful AES-GCM
decode is the unambiguous "found" signal that ends the search early.

## Trade-offs

- Brute-force resync is simple and exact within the bounds but scales poorly
  with the search range; out-of-bounds distortions are missed (documented).
- Invariant-domain methods (Fourier–Mellin) handle arbitrary rotation/scale but
  are intricate and can lose capacity/robustness; templates add an attackable
  synchronization signal. We chose bounded search to match a realistic threat
  model with predictable cost.

## References

- J. J. K. Ó Ruanaidh, T. Pun, "Rotation, scale and translation invariant
  spread spectrum digital image watermarking", *Signal Processing*, 66(3), 1998.
  https://doi.org/10.1016/S0165-1684(98)00012-7
- C.-Y. Lin, M. Wu, J. A. Bloom, I. J. Cox, M. L. Miller, Y. M. Lui, "Rotation,
  Scale, and Translation Resilient Watermarking for Images", *IEEE Trans. Image
  Processing*, 10(5), 2001. https://doi.org/10.1109/83.918569
- S. Pereira, T. Pun, "Robust Template Matching for Affine Resistant Image
  Watermarks", *IEEE Trans. Image Processing*, 9(6), 2000.
  https://doi.org/10.1109/83.846253
- M. Kutter, "Watermarking resisting to translation, rotation, and scaling",
  *Proc. SPIE 3528, Multimedia Systems and Applications*, 1999.
  https://doi.org/10.1117/12.337432
