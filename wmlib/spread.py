# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Key-driven spread-spectrum carrier plan.

Each payload bit is spread over many DCT coefficients ("carriers") scattered
across the image. A secret PRNG subkey decides, for every carrier, which bit it
carries and with what antipodal sign ("chip"). Detection correlates the received
coefficients against the same key-derived chips, so it is *blind* (no original
document needed) and unreadable without the key.

The plan is defined over a fixed TILE x TILE grid of 8x8 blocks and repeated
across the whole image. That periodicity gives two things:

  * redundancy — a cropped image still contains whole tiles, hence full copies
    of the payload;
  * resynchronization — a translation can be recovered by trying the TILE x TILE
    candidate offsets (see :mod:`wmlib.extract`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Tile size in 8x8 blocks. TILE*TILE*len(MID_BAND) carriers must exceed the
# payload bit count so one tile holds a full codeword copy.
TILE = 16

# Mid-frequency coefficient positions (row, col) within an 8x8 DCT block.
# Low enough to survive JPEG at q>=50, high enough to stay invisible.
#
# Two DISJOINT bands so the keyed forensic mark and the public "if found,
# contact" mark live on different coefficients and do not interfere.
MID_BAND: tuple[tuple[int, int], ...] = ((1, 2), (2, 1), (2, 2), (1, 3))
MID_BAND_PUBLIC: tuple[tuple[int, int], ...] = ((3, 1), (1, 4), (2, 3), (3, 2))


@dataclass(frozen=True)
class CarrierPlan:
    """Per-tile assignment of carriers to payload bits.

    Arrays are shaped (TILE, TILE, n_slots); ``bit_index[r, c, s]`` is the
    payload bit carried by slot ``s`` of the block at tile-local (r, c), and
    ``chip[r, c, s]`` is its +-1 sign.
    """

    bit_index: np.ndarray  # int64
    chip: np.ndarray  # float64, values in {-1, +1}
    n_bits: int


def _rng(prng_key: bytes) -> np.random.Generator:
    """Deterministic Generator seeded from the PRNG subkey."""
    seed = np.frombuffer(prng_key, dtype=np.uint32)
    return np.random.default_rng(seed)


def build_plan(prng_key: bytes, n_bits: int, n_slots: int = len(MID_BAND)) -> CarrierPlan:
    """Build the carrier plan for ``n_bits`` payload bits over ``n_slots`` carriers/block.

    Carriers are assigned to bits as evenly as possible, then permuted, so the
    spreading is balanced but unpredictable without the key.
    """
    n_carriers = TILE * TILE * n_slots
    if n_carriers < n_bits:
        raise ValueError(
            f"tile holds {n_carriers} carriers but payload needs {n_bits} bits; "
            "increase TILE or MID_BAND"
        )

    rng = _rng(prng_key)
    # Balanced assignment: each bit appears ~equally, then shuffled.
    base = np.arange(n_carriers) % n_bits
    rng.shuffle(base)
    chips = rng.choice(np.array([-1.0, 1.0]), size=n_carriers)

    bit_index = base.reshape(TILE, TILE, n_slots)
    chip = chips.reshape(TILE, TILE, n_slots)
    return CarrierPlan(bit_index=bit_index, chip=chip, n_bits=n_bits)


def tile_maps(
    plan: CarrierPlan, nby: int, nbx: int, offset: tuple[int, int] = (0, 0)
) -> tuple[np.ndarray, np.ndarray]:
    """Expand a per-tile plan to full (nby, nbx, n_slots) maps for an image.

    ``offset`` shifts the tile origin (used during resynchronization search):
    block (i, j) maps to tile-local ((i + dr) % TILE, (j + dc) % TILE).
    """
    dr, dc = offset
    rows = (np.arange(nby) + dr) % TILE
    cols = (np.arange(nbx) + dc) % TILE
    bit_map = plan.bit_index[np.ix_(rows, cols)]
    chip_map = plan.chip[np.ix_(rows, cols)]
    return bit_map, chip_map
