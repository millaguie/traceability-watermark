# Technical documentation

This folder explains the techniques behind the traceability watermark, one
document per technique. Each page covers *what it is*, *how this project uses
it* (with links to the source), the *trade-offs*, and *references* (papers that
introduce or implement the idea).

For usage, the threat model and guarantees, see the top-level
[README](../README.md).

## The pipeline at a glance

```
recipient id ──► AES-256-GCM ──► Reed–Solomon ──► spread-spectrum bits
                  (encrypt+auth)   (error correct)        │
                                                          ▼
        image ──► YCbCr ──► 8×8 block-DCT ──► modulate mid-band coeffs
                                                  (perceptual mask, headroom)
                                                          │
                                                          ▼
                                                  watermarked image

watermarked image ──► block-DCT ──► correlate vs key chips ──► votes
                          ▲                                       │
              geometric / pixel / tile resync                     ▼
                                                  Reed–Solomon ──► GCM verify ──► id
```

## Techniques

| Document | What | Source |
| --- | --- | --- |
| [spread-spectrum.md](spread-spectrum.md) | Spreading each bit over many DCT coefficients with key-driven ± chips | [spread.py](../wmlib/spread.py), [embed.py](../wmlib/embed.py) |
| [dct-domain.md](dct-domain.md) | Why embed in the 8×8 block-DCT of luminance | [transform.py](../wmlib/transform.py) |
| [blind-detection.md](blind-detection.md) | Recovering bits with no original, via correlation + phase-bin pooling | [extract.py](../wmlib/extract.py) |
| [geometric-synchronization.md](geometric-synchronization.md) | Surviving crop / translation / rotation / scale | [api.py](../wmlib/api.py), [imageops.py](../wmlib/imageops.py) |
| [scale-invariance.md](scale-invariance.md) | Surviving messenger downscaling (Telegram/WhatsApp) via canonical normalization | [api.py](../wmlib/api.py), [imageops.py](../wmlib/imageops.py) |
| [perceptual-masking.md](perceptual-masking.md) | Hiding the mark using the human visual system + luminance headroom | [embed.py](../wmlib/embed.py) |
| [reed-solomon.md](reed-solomon.md) | Byte-level forward error correction | [payload.py](../wmlib/payload.py) |
| [authenticated-encryption.md](authenticated-encryption.md) | AES-256-GCM: confidentiality + forgery resistance | [payload.py](../wmlib/payload.py) |
| [key-derivation.md](key-derivation.md) | HKDF subkeys + key sourcing | [keys.py](../wmlib/keys.py) |
| [payload-format.md](payload-format.md) | Framing, fixed-length codewords, dual forensic/public channels | [payload.py](../wmlib/payload.py), [payload_public.py](../wmlib/payload_public.py) |
| [pdf-flattening.md](pdf-flattening.md) | Marking PDFs without a removable overlay layer | [pdf.py](../wmlib/pdf.py) |
| [visible-watermark.md](visible-watermark.md) | Legacy visible mosaic (deterrent only) | [visible.py](../wmlib/visible.py) |

## A note on references

Citations give authors, title, venue and year; DOIs/URLs are included where
stable (RFC, NIST, DOI). They are best-effort pointers for learning — verify the
exact edition for formal work.
