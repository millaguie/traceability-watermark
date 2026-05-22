# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Image attacks used by the robustness harness.

Each takes and returns a uint8 HxWx3 RGB array. They are deliberately the kind
of degradations a recipient might apply before leaking a document.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageFilter

from wmlib import imageops


def jpeg(image: np.ndarray, quality: int) -> np.ndarray:
    """Round-trip through JPEG at the given quality factor."""
    buf = io.BytesIO()
    Image.fromarray(image).save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return np.asarray(Image.open(buf).convert("RGB"))


def rescale(image: np.ndarray, factor: float) -> np.ndarray:
    """Resize by ``factor`` and leave it resized (attacker does not restore)."""
    return imageops.resample(image, scale=factor)


def crop(image: np.ndarray, fraction: float) -> np.ndarray:
    """Crop ``fraction`` off every edge (e.g. 0.1 -> remove 10% per side)."""
    h, w = image.shape[:2]
    dh, dw = int(h * fraction), int(w * fraction)
    return image[dh : h - dh, dw : w - dw]


def rotate(image: np.ndarray, degrees: float) -> np.ndarray:
    return imageops.resample(image, angle=degrees)


def gaussian_noise(image: np.ndarray, sigma: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    noisy = image.astype(np.float64) + rng.normal(0, sigma, size=image.shape)
    return np.clip(noisy, 0, 255).astype(np.uint8)


def blur(image: np.ndarray, radius: float) -> np.ndarray:
    return np.asarray(Image.fromarray(image).filter(ImageFilter.GaussianBlur(radius)))


# Catalogue: name -> callable(image) for the harness/measurement.
ATTACKS = {
    "jpeg_q75": lambda im: jpeg(im, 75),
    "jpeg_q50": lambda im: jpeg(im, 50),
    "scale_0.8": lambda im: rescale(im, 0.8),
    "scale_1.2": lambda im: rescale(im, 1.2),
    "crop_10pct": lambda im: crop(im, 0.10),
    "rotate_+2deg": lambda im: rotate(im, 2.0),
    "rotate_-2deg": lambda im: rotate(im, -2.0),
    "noise_sigma5": lambda im: gaussian_noise(im, 5.0),
    "blur_r1": lambda im: blur(im, 1.0),
}
