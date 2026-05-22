# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Shared fixtures and helpers for watermark tests."""
from __future__ import annotations

import numpy as np
import pytest

KEY = bytes.fromhex("ab" * 32)


def make_textured_image(h: int = 512, w: int = 512, seed: int = 7) -> np.ndarray:
    """Deterministic, document-like textured RGB image (uint8 HxWx3).

    Mixes smooth gradients, sinusoidal texture, a few solid rectangles and mild
    noise — enough local activity to exercise the perceptual mask realistically,
    unlike a flat fill.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    base = (
        128
        + 60 * np.sin(2 * np.pi * xx / 64)
        + 40 * np.cos(2 * np.pi * yy / 48)
        + 0.05 * xx
    )
    base += rng.normal(0, 6, size=(h, w))  # mild grain
    # A couple of flat "fields" like ID-card regions.
    base[h // 8 : h // 3, w // 8 : w // 2] = 230
    base[h // 2 : h // 2 + h // 6, w // 4 : w // 4 + w // 3] = 40
    base = np.clip(base, 0, 255)
    rgb = np.stack([base, np.roll(base, 5, axis=1), np.roll(base, -5, axis=0)], axis=-1)
    return np.clip(rgb, 0, 255).astype(np.uint8)


@pytest.fixture
def image():
    return make_textured_image()


@pytest.fixture
def key():
    return KEY
