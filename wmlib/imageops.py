# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Small image-geometry and I/O helpers shared across the package."""
from __future__ import annotations

import os

import numpy as np
from PIL import Image

_RESAMPLE = Image.Resampling.BICUBIC


def resize_rgb(image_rgb: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize a uint8 RGB array to (width, height) with high-quality resampling."""
    return np.asarray(Image.fromarray(image_rgb).resize((width, height), Image.Resampling.LANCZOS))


def resize_delta(delta: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize a float HxWxC watermark delta to (width, height), per channel.

    Lanczos (not bilinear) is used so the mid-frequency carriers that hold the
    watermark survive the resample back to native resolution — bilinear is too
    low-pass and erases a weak mark (e.g. on near-white document scans).
    """
    out = np.empty((height, width, delta.shape[2]), dtype=np.float32)
    for c in range(delta.shape[2]):
        plane = Image.fromarray(delta[..., c].astype(np.float32), mode="F")
        out[..., c] = np.asarray(plane.resize((width, height), Image.Resampling.LANCZOS))
    return out


def load_rgb(path: str | os.PathLike[str]) -> np.ndarray:
    """Load an image file as a uint8 HxWx3 RGB array."""
    return np.asarray(Image.open(path).convert("RGB"))


def save_rgb(image_rgb: np.ndarray, path: str | os.PathLike[str]) -> None:
    """Save a uint8 RGB array; JPEG outputs use high quality."""
    img = Image.fromarray(image_rgb)
    ext = os.path.splitext(str(path))[1].lower()
    if ext in (".jpg", ".jpeg"):
        img.save(path, quality=95)
    else:
        img.save(path)


def resample(image_rgb: np.ndarray, *, scale: float = 1.0, angle: float = 0.0) -> np.ndarray:
    """Return ``image_rgb`` rescaled by ``scale`` then rotated by ``angle`` deg.

    Used both to apply geometric attacks in tests and to apply candidate
    geometric *corrections* during blind detection.
    """
    img = Image.fromarray(image_rgb)
    if scale != 1.0:
        w, h = img.size
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), _RESAMPLE)
    if angle != 0.0:
        # expand=False keeps the frame size: a rotation correction must not
        # change dimensions (under scale normalization a size change would look
        # like a spurious scale), and in-place rotation is the realistic deskew
        # model for a leaked document (no tell-tale black border triangles).
        img = img.rotate(angle, resample=_RESAMPLE, expand=False)
    return np.asarray(img)
