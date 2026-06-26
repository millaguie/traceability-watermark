# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Color-space and block-DCT helpers used by the robust watermark.

We embed in the luminance (Y) channel of YCbCr (BT.601), in the mid-frequency
band of 8x8 DCT blocks — the same domain JPEG operates in, which is what makes
the mark survive recompression. All math is done in float64.
"""

from __future__ import annotations

import numpy as np
from scipy.fft import dctn, idctn

BLOCK = 8

# BT.601 forward/inverse matrices (full-range, 0..255).
_RGB2YCC = np.array(
    [
        [0.299, 0.587, 0.114],
        [-0.168736, -0.331264, 0.5],
        [0.5, -0.418688, -0.081312],
    ]
)
_YCC2RGB = np.linalg.inv(_RGB2YCC)


def rgb_to_ycc(rgb: np.ndarray) -> np.ndarray:
    """Convert an HxWx3 uint8/float RGB array to float YCbCr (Y in 0..255)."""
    rgb = rgb.astype(np.float64)
    ycc = rgb @ _RGB2YCC.T
    ycc[..., 1:] += 128.0  # center chroma
    return ycc


def ycc_to_rgb(ycc: np.ndarray) -> np.ndarray:
    """Convert float YCbCr back to a uint8 HxWx3 RGB array."""
    ycc = ycc.copy()
    ycc[..., 1:] -= 128.0
    rgb = ycc @ _YCC2RGB.T
    return np.clip(np.round(rgb), 0, 255).astype(np.uint8)


def pad_to_blocks(channel: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
    """Pad a 2D channel (edge replication) so both dims are multiples of BLOCK.

    Returns the padded channel and the original (height, width) for cropping
    back after processing.
    """
    h, w = channel.shape
    ph = (-h) % BLOCK
    pw = (-w) % BLOCK
    if ph or pw:
        channel = np.pad(channel, ((0, ph), (0, pw)), mode="edge")
    return channel, (h, w)


def to_blocks(channel: np.ndarray) -> np.ndarray:
    """Reshape an HxW (multiple of BLOCK) channel into (nby, nbx, 8, 8)."""
    h, w = channel.shape
    nby, nbx = h // BLOCK, w // BLOCK
    return channel.reshape(nby, BLOCK, nbx, BLOCK).transpose(0, 2, 1, 3).copy()


def from_blocks(blocks: np.ndarray) -> np.ndarray:
    """Inverse of :func:`to_blocks`."""
    nby, nbx = blocks.shape[:2]
    return blocks.transpose(0, 2, 1, 3).reshape(nby * BLOCK, nbx * BLOCK)


def dct_blocks(blocks: np.ndarray) -> np.ndarray:
    """Orthonormal 2D DCT over the last two axes of a block array."""
    return dctn(blocks, axes=(-2, -1), norm="ortho")


def idct_blocks(coeffs: np.ndarray) -> np.ndarray:
    """Inverse of :func:`dct_blocks`."""
    return idctn(coeffs, axes=(-2, -1), norm="ortho")
