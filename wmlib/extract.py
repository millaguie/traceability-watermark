# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Blind detection of the spread-spectrum watermark.

No original document is required. Detection correlates each carrier coefficient
against its key-derived chip and accumulates a soft vote per payload bit; the
sign of each vote is the recovered bit, and the vote energy is a confidence
score used to pick the right synchronization without decoding everywhere.

Synchronization is a translation search over one tile period (TILE blocks =
TILE*8 px). To make that search cheap, we exploit the embedding's periodicity:
all blocks sharing the same position modulo TILE ("phase bin") can be summed
*once* per pixel origin; each of the TILE*TILE tile offsets is then a tiny
operation over a TILE x TILE x n_slots array, independent of image size.

The geometric (rotation/scale) part of the search is driven by :mod:`wmlib.api`.
"""

from __future__ import annotations

import numpy as np

from . import transform
from .spread import TILE, CarrierPlan, MID_BAND, tile_maps


def block_coeffs(image_rgb: np.ndarray, origin: tuple[int, int] = (0, 0)) -> np.ndarray:
    """DCT coefficients (nby, nbx, 8, 8) of the luminance channel.

    ``origin`` shifts the 8x8 block grid by (sy, sx) pixels, used to recover the
    sub-block misalignment a crop or rotation introduces.
    """
    sy, sx = origin
    ycc = transform.rgb_to_ycc(image_rgb)
    y = ycc[..., 0]
    if sy or sx:
        y = y[sy:, sx:]
    y_padded, _ = transform.pad_to_blocks(y)
    return transform.dct_blocks(transform.to_blocks(y_padded))


def _phase_selector(n: int, period: int) -> np.ndarray:
    """One-hot matrix (period, n) selecting indices by ``index % period``."""
    sel = np.zeros((period, n))
    idx = np.arange(n)
    sel[idx % period, idx] = 1.0
    return sel


def phase_sums(
    coeffs: np.ndarray, band: tuple[tuple[int, int], ...] = MID_BAND
) -> np.ndarray:
    """Pool carrier coefficients into TILE x TILE phase bins, per slot.

    Returns an array of shape (TILE, TILE, n_slots). ``S[a, b, s]`` is the sum
    of slot ``s``'s mid-band coefficient over every block whose grid position is
    congruent to (a, b) modulo TILE. Computed once, reused for all tile offsets.
    """
    nby, nbx = coeffs.shape[:2]
    mr = _phase_selector(nby, TILE)  # (TILE, nby)
    mc = _phase_selector(nbx, TILE).T  # (nbx, TILE)
    sums = np.empty((TILE, TILE, len(band)))
    for slot, (pr, pc) in enumerate(band):
        sums[..., slot] = mr @ coeffs[:, :, pr, pc] @ mc
    return sums


def vote_from_phase(
    sums: np.ndarray, plan: CarrierPlan, offset: tuple[int, int]
) -> np.ndarray:
    """Votes per payload bit for a tile ``offset``, from pooled phase sums."""
    dr, dc = offset
    chip = np.roll(plan.chip, shift=(-dr, -dc), axis=(0, 1))  # (T, T, n_slots)
    bit_index = np.roll(plan.bit_index, shift=(-dr, -dc), axis=(0, 1))
    contrib = (chip * sums).ravel()
    return np.bincount(bit_index.ravel(), weights=contrib, minlength=plan.n_bits)


def best_offset_votes(
    coeffs: np.ndarray, plan: CarrierPlan, band: tuple[tuple[int, int], ...] = MID_BAND
) -> tuple[np.ndarray, float]:
    """Votes and confidence at the highest-energy tile offset for one image.

    Correct synchronization yields markedly higher vote energy than misaligned
    offsets, so the winner found here is the one worth decoding.
    """
    sums = phase_sums(coeffs, band)
    best_votes = np.zeros(plan.n_bits)
    best_score = -1.0
    for dr in range(TILE):
        for dc in range(TILE):
            v = vote_from_phase(sums, plan, (dr, dc))
            score = float(np.dot(v, v))
            if score > best_score:
                best_score, best_votes = score, v
    return best_votes, best_score


def votes_to_bits(votes: np.ndarray) -> np.ndarray:
    """Hard-decision: positive vote -> bit 1, else 0."""
    return (votes > 0).astype(np.uint8)


def vote(
    coeffs: np.ndarray,
    plan: CarrierPlan,
    offset: tuple[int, int],
    band: tuple[tuple[int, int], ...] = MID_BAND,
) -> np.ndarray:
    """Reference (non-pooled) vote for a single tile offset. Used in tests."""
    nby, nbx = coeffs.shape[:2]
    bit_map, chip_map = tile_maps(plan, nby, nbx, offset)
    votes = np.zeros(plan.n_bits)
    for slot, (pr, pc) in enumerate(band):
        contrib = (chip_map[..., slot] * coeffs[:, :, pr, pc]).ravel()
        votes += np.bincount(
            bit_map[..., slot].ravel(), weights=contrib, minlength=plan.n_bits
        )
    return votes
