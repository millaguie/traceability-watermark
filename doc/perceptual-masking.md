# Perceptual masking and luminance headroom

## What it is

The Human Visual System (HVS) is not uniformly sensitive: it tolerates larger
changes in **busy, textured, high-contrast** regions (visual *masking*) and
notices small changes in **smooth, flat** regions. Perceptual watermarking uses
an HVS model to shape the watermark strength spatially and spectrally, embedding
*more* energy where it hides and *less* where it would show — maximizing
robustness for a fixed perceptual budget (and vice-versa).

## How this project uses it

[`embed.py`](../wmlib/embed.py) applies two complementary ideas:

1. **Texture masking.** Each 8×8 block gets a strength multiplier from its local
   activity: `mask = clip(block_std / median(block_std), 0.4, 2.5)`
   (`_perceptual_mask`). Flat blocks get a small multiplier (changes there are
   visible); textured blocks tolerate more. The embedding strength becomes
   `α · mask`. Detection is unaffected: a positive per-carrier weight only
   changes the confidence weighting, not the sign that carries the bit.

2. **Luminance headroom.** Before embedding, Y is compressed into
   `[headroom, 255−headroom]` (default `headroom = 10`). On **high-key documents**
   (scanned forms, ID cards — mostly near-white) the luminance saturates at 255,
   so positive watermark excursions get *clipped* and the mark is destroyed.
   Reserving headroom stops the clipping. This was the fix that took a near-white
   page from an uncorrectable ~3% bit-error rate down to ~0.1%.

Quality is verified with SSIM/PSNR in the tests (target SSIM ≥ 0.98 for a single
mark on textured content; ≥ 0.96 with both forensic + contact marks stacked).

## Trade-offs

- The mask here is a simple variance proxy, not a full DCT-domain HVS model
  (e.g. Watson's). It is cheap, robust and good enough; a Watson-style
  just-noticeable-difference model could improve the invisibility/robustness
  curve at more cost.
- Headroom slightly reduces global contrast (white → ~245). Imperceptible on
  documents, and a worthwhile trade for surviving high-key inputs.

## References

- A. B. Watson, "DCT quantization matrices visually optimized for individual
  images", *Proc. SPIE 1913*, 1993. https://doi.org/10.1117/12.152694
- C. I. Podilchuk, W. Zeng, "Image-Adaptive Watermarking Using Visual Models",
  *IEEE J. Selected Areas in Communications*, 16(4), 1998.
  https://doi.org/10.1109/49.668975
- M. Barni, F. Bartolini, A. Piva, "Improved wavelet-based watermarking through
  pixel-wise masking", *IEEE Trans. Image Processing*, 10(5), 2001.
  https://doi.org/10.1109/83.918570
