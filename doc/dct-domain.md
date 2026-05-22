# Embedding in the block-DCT of luminance

## What it is

The Discrete Cosine Transform (DCT) expresses a block of pixels as a sum of
cosine basis functions at increasing spatial frequencies. The 8×8 block-DCT is
the heart of JPEG: an image is split into 8×8 blocks and each is transformed,
giving one **DC** coefficient (block average) and 63 **AC** coefficients
ordered low → high frequency.

Watermarking in this domain is attractive because:

- it is the **same domain JPEG quantizes**, so an embedding that respects JPEG's
  surviving coefficients survives recompression;
- frequency bands map to human perception — low frequencies are visually
  salient, very high frequencies are fragile (quantized/filtered away), and the
  **mid band** is the sweet spot: robust yet not very visible.

## How this project uses it

[`transform.py`](../wmlib/transform.py):

1. **Color space.** The image is converted to YCbCr (BT.601) and the mark is
   embedded only in the **luminance Y** channel — the eye is most forgiving of
   chrominance changes, but luminance survives grayscale conversion and most
   processing, so it is the robust choice.
2. **Blocking.** Y is padded to a multiple of 8 and split into 8×8 blocks
   (`to_blocks`).
3. **Transform.** An orthonormal 2-D DCT is applied per block
   (`dct_blocks`, via `scipy.fft.dctn(..., norm="ortho")`).
4. **Mid-band carriers.** A fixed set of mid-frequency positions carries the
   mark: `MID_BAND = ((1,2),(2,1),(2,2),(1,3))` for the forensic mark and a
   disjoint `MID_BAND_PUBLIC = ((3,1),(1,4),(2,3),(3,2))` for the public contact
   mark (see [spread.py](../wmlib/spread.py)). These avoid the DC term (visible)
   and the highest frequencies (JPEG-fragile).

The inverse path (`idct_blocks`, `from_blocks`, `ycc_to_rgb`) reconstructs the
watermarked image.

## Trade-offs

- Block-DCT is cheap and JPEG-aligned, but **block-based** schemes are sensitive
  to de-synchronization (a crop that shifts the 8×8 grid) — handled in
  [geometric-synchronization](geometric-synchronization.md).
- A wavelet (DWT) domain can be more robust to scaling/filtering, and DWT-DCT
  hybrids are common; we chose plain block-DCT for simplicity and JPEG-domain
  robustness and verified it meets the threat model.

## References

- N. Ahmed, T. Natarajan, K. R. Rao, "Discrete Cosine Transform", *IEEE Trans.
  Computers*, C-23(1), 1974. https://doi.org/10.1109/T-C.1974.223784
- G. K. Wallace, "The JPEG Still Picture Compression Standard", *Communications
  of the ACM*, 34(4), 1991. https://doi.org/10.1145/103085.103089
- M. Barni, F. Bartolini, V. Cappellini, A. Piva, "A DCT-domain system for
  robust image watermarking", *Signal Processing*, 66(3), 1998.
  https://doi.org/10.1016/S0165-1684(98)00015-2
- A. B. Watson, "DCT quantization matrices visually optimized for individual
  images", *Proc. SPIE 1913, Human Vision, Visual Processing, and Digital
  Display IV*, 1993. https://doi.org/10.1117/12.152694
