# Scale invariance by canonical normalization

## What it is

Block-DCT watermarks are tied to an 8×8 pixel grid, so **rescaling** the image
changes the grid spacing and de-synchronizes detection. A bounded search
([geometric-synchronization](geometric-synchronization.md)) only covers small
scale changes (±20% here). But messaging platforms and social networks apply a
*large, fixed* downscale: when you send a photo, **Telegram caps the long side
to ~1280 px**, WhatsApp/Instagram to ~1024–1600, etc. A 2000 px scan sent
through Telegram comes back at ~1280 px — a 0.64× scale, far outside ±20%, so a
naive block-DCT mark is destroyed.

The fix is **scale invariance by normalization**: tie the watermark to a fixed
*canonical resolution* rather than to the image's native pixel count. If both
embedding and detection always reference the same canonical grid, any
aspect-preserving rescale the platform applies cancels out — embed-grid and
detect-grid coincide regardless of the intermediate size.

## How this project uses it

[`api.py`](../wmlib/api.py), `CANONICAL_LONG_SIDE = 1024`:

- **Embed** (`_normalized_embed`): resize the image to the canonical size
  (long side = 1024, aspect preserved, multiple of 8), run the spread-spectrum
  embed there, then upsample **only the watermark delta** back to the native
  resolution and add it to the untouched original. Carrying just the delta keeps
  the host content free of resample blur (SSIM ≈ 0.99) while the mark lives on
  the canonical grid. The delta is resampled with **Lanczos** (not bilinear) so
  the mid-band carriers survive the round trip even on weak/near-white scans.
  Inputs *smaller* than canonical are embedded and returned at canonical size
  (upscaling them would otherwise downsample the delta and lose the mark).
- **Detect** (`_to_canonical` in `extract_image` / `extract_contact` /
  `recover_bits`): resize the received image to the canonical long side, then
  run the blind detector. Whatever scaling the platform did is undone here.

Measured (`tools/measure_robustness.py`, [`tests/test_robustness.py`](../tests/test_robustness.py)):
a 2000 px image embedded this way and pushed through a simulated messenger
pipeline (downscale + JPEG) still recovers the authenticated id at 1280 px and
1024 px caps. Two permanent guards exist: `messenger_1280` in the attack
catalogue and `test_survives_messenger_downscale`.

Side effects of normalizing at both ends:

- detection always runs on a ≤1024 px image, so extraction cost is bounded
  regardless of the input's native resolution;
- a **PDF DPI mismatch** between embed and extract (also just a scale change) is
  largely absorbed;
- **cropping** becomes a small *scale* change after normalization (removing a
  fraction `f` per edge scales the grid by `1/(1−2f)`), so the default search
  grid includes the matching scale corrections (down to ~0.8, i.e. ~12% crop)
  rather than relying on translation alone.

## Trade-offs

- Normalization assumes the platform **preserves aspect ratio** (scaling does;
  non-proportional cropping does not — small crops are still handled by the
  offset search, large ones break the assumption).
- The mark is embedded at ≤1024-equivalent resolution, slightly lowering spatial
  capacity, but redundancy and error correction remain ample.
- Extreme downscales (≲0.3×) and repeated aggressive recompression can still
  defeat it; sending a document **"as file"** (lossless) on messengers avoids
  the whole problem and is the recommended path for the most sensitive cases.

## References

- J. J. K. Ó Ruanaidh, T. Pun, "Rotation, scale and translation invariant
  spread spectrum digital image watermarking", *Signal Processing*, 66(3), 1998.
  https://doi.org/10.1016/S0165-1684(98)00012-7 — invariance via the
  Fourier–Mellin domain (the heavyweight alternative to normalization).
- C.-Y. Lin, M. Wu, J. A. Bloom, I. J. Cox, M. L. Miller, Y. M. Lui, "Rotation,
  Scale, and Translation Resilient Watermarking for Images", *IEEE Trans. Image
  Processing*, 10(5), 2001. https://doi.org/10.1109/83.918569
- D. Zheng, Y. Liu, J. Zhao, A. El Saddik, "A survey of RST invariant image
  watermarking algorithms", *ACM Computing Surveys*, 39(2), 2007.
  https://doi.org/10.1145/1242471.1242473
