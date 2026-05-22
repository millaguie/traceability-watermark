# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Spread-spectrum embedding of a payload bitstream into an image.

Operates purely on bits: the payload codec (:mod:`wmlib.payload`) and key
handling (:mod:`wmlib.keys`) live elsewhere. This keeps the signal-processing
core independently testable.
"""
from __future__ import annotations

import numpy as np

from . import transform
from .spread import CarrierPlan, MID_BAND, build_plan, tile_maps

# Luminance headroom (in 0..255 units) reserved before embedding. Compressing
# Y into [HEADROOM, 255-HEADROOM] stops bright regions from clipping at 255,
# which would otherwise destroy the mark on high-key documents (scans, forms).
HEADROOM = 10


def _perceptual_mask(y_blocks: np.ndarray) -> np.ndarray:
    """Per-block strength multiplier from local activity (texture masking).

    Smooth blocks get a smaller multiplier (changes would be visible there);
    busy blocks tolerate more. Returns an (nby, nbx) array of positive weights.
    """
    activity = y_blocks.std(axis=(-2, -1))
    ref = float(np.median(activity)) + 1e-6
    return np.clip(activity / ref, 0.4, 2.5)


def embed_bits(
    image_rgb: np.ndarray,
    payload_bits: np.ndarray,
    prng_key: bytes,
    *,
    alpha: float = 7.0,
    headroom: int = HEADROOM,
    band: tuple[tuple[int, int], ...] = MID_BAND,
    plan: CarrierPlan | None = None,
) -> np.ndarray:
    """Embed ``payload_bits`` (0/1 array) into ``image_rgb`` (HxWx3 uint8).

    ``band`` selects which 8x8 DCT coefficients carry the mark; use a disjoint
    band to embed an independent watermark that does not interfere.

    Returns a new watermarked uint8 RGB image of the same size.
    """
    bits = np.asarray(payload_bits, dtype=np.int64)
    n_bits = bits.size
    if plan is None:
        plan = build_plan(prng_key, n_bits, len(band))

    ycc = transform.rgb_to_ycc(image_rgb)
    # Reserve headroom so bright regions don't clip away the mark.
    ycc[..., 0] = headroom + ycc[..., 0] * (255 - 2 * headroom) / 255.0
    y_padded, (h, w) = transform.pad_to_blocks(ycc[..., 0])
    blocks = transform.to_blocks(y_padded)
    nby, nbx = blocks.shape[:2]

    mask = _perceptual_mask(blocks)  # (nby, nbx)
    coeffs = transform.dct_blocks(blocks)

    bit_map, chip_map = tile_maps(plan, nby, nbx)  # (nby, nbx, n_slots)
    # s in {-1, +1}; +alpha pushes the carrier toward the bit's sign.
    signs = (2 * bits - 1).astype(np.float64)

    for slot, (pr, pc) in enumerate(band):
        s_map = signs[bit_map[..., slot]]  # (nby, nbx)
        delta = alpha * mask * chip_map[..., slot] * s_map
        coeffs[:, :, pr, pc] += delta

    y_marked = transform.from_blocks(transform.idct_blocks(coeffs))[:h, :w]
    ycc[..., 0] = y_marked
    return transform.ycc_to_rgb(ycc)
