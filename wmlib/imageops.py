# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Small image-geometry and I/O helpers shared across the package."""
from __future__ import annotations

import os

import numpy as np
from PIL import Image

_RESAMPLE = Image.Resampling.BICUBIC


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
        img = img.rotate(angle, resample=_RESAMPLE, expand=True)
    return np.asarray(img)
