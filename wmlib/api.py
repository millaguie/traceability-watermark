# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""High-level embed/extract API tying together keys, payload and signal core.

This is the layer the CLI and PDF handler call. It hides the spread-spectrum
details and the geometric resynchronization search.

Two independent marks can coexist in one image, on disjoint DCT coefficient
bands so they do not interfere:

  * the **forensic** mark — keyed, AES-GCM authenticated recipient id
    (:func:`embed_image` / :func:`extract_image`);
  * the **public contact** mark — unencrypted "if found, contact ..." string
    readable without any key (:func:`embed_contact` / :func:`extract_contact`).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import embed as _embed
from . import extract as _extract
from . import imageops, payload, payload_public
from .keys import derive_subkeys
from .spread import MID_BAND, MID_BAND_PUBLIC, build_plan
from .transform import BLOCK

# Geometric *corrections* tried during blind detection. After scale
# normalization, pure rescaling (incl. messenger downscaling) is already undone,
# so the residual scale to search for comes mainly from CROPPING: removing a
# fraction f per edge and re-normalizing scales the grid by 1/(1-2f). The grid
# below covers up to ~12% per-edge crop (scale 0.8) plus +-2deg rotation.
FAST_SCALES: tuple[float, ...] = (1.0, 0.9, 0.8)
FAST_ANGLES: tuple[float, ...] = (0.0, -2.0, 2.0)
FULL_SCALES: tuple[float, ...] = (1.0, 0.95, 0.9, 0.85, 0.8, 1.1, 1.25)
FULL_ANGLES: tuple[float, ...] = (0.0, -1.0, 1.0, -2.0, 2.0)

# Fixed, published PRNG key for the public contact channel: it carries no
# secret, so anyone with the tool can locate and read it.
PUBLIC_PRNG_KEY = hashlib.sha256(b"watermark/public/v1").digest()

# Canonical long side (px) for scale normalization. Embedding and detection both
# reference this fixed resolution, so any aspect-preserving rescaling a platform
# applies (e.g. Telegram capping a photo to ~1280 px) cancels out — the mark is
# tied to the canonical grid, not the native pixel count. 1024 sits below common
# messenger caps (margin) while leaving ample carrier redundancy.
CANONICAL_LONG_SIDE = 1024


def _canonical_size(width: int, height: int) -> tuple[int, int]:
    """Aspect-preserving size with the long side = CANONICAL_LONG_SIDE (mult. of 8)."""
    s = CANONICAL_LONG_SIDE / max(width, height)
    cw = max(BLOCK, int(round(width * s)) // BLOCK * BLOCK)
    ch = max(BLOCK, int(round(height * s)) // BLOCK * BLOCK)
    return cw, ch


def _to_canonical(image_rgb: np.ndarray) -> np.ndarray:
    """Resize an image to the canonical grid for detection."""
    h, w = image_rgb.shape[:2]
    cw, ch = _canonical_size(w, h)
    return imageops.resize_rgb(image_rgb, cw, ch)


def _normalized_embed(
    image_rgb: np.ndarray, embed_fn: Callable[[np.ndarray], np.ndarray]
) -> np.ndarray:
    """Embed on the canonical grid, then carry only the watermark delta back.

    ``embed_fn`` watermarks the canonical-resolution copy. We add only the
    upsampled *delta* to the original, so the host content stays pristine (no
    resample blur) and the mark lives on the scale-invariant canonical grid.
    """
    h, w = image_rgb.shape[:2]
    cw, ch = _canonical_size(w, h)
    small = imageops.resize_rgb(image_rgb, cw, ch)
    marked_small = embed_fn(small)

    if max(w, h) < CANONICAL_LONG_SIDE:
        # Input smaller than canonical: we had to upscale to embed. Returning the
        # mark at native resolution would downsample the delta and destroy the
        # carriers, so we return at canonical resolution instead (the output is
        # larger than the input — documented behavior for small inputs).
        return marked_small

    # Input >= canonical: carry only the watermark delta back to the native
    # resolution, leaving the host content untouched (no resample blur).
    delta = marked_small.astype(np.float32) - small.astype(np.float32)
    delta_full = imageops.resize_delta(delta, w, h)
    return np.clip(image_rgb.astype(np.float32) + delta_full, 0, 255).astype(np.uint8)


@dataclass
class SearchSpec:
    """Resynchronization search space for extraction.

    Defaults to a fast search (boundary geometries, every other pixel origin),
    which covers the documented attack envelope cheaply. :meth:`full` returns
    the exhaustive search for the rare case the fast one misses a mark.
    """

    scales: tuple[float, ...] = FAST_SCALES
    angles: tuple[float, ...] = FAST_ANGLES
    # Whether to search rotation/scale at all. The default grid is cheap because
    # detection always runs on the canonical (<=1024 px) image, so it is on by
    # default and covers scale, ~10% cropping (which normalization turns into a
    # scale) and +-2deg rotation. Set False for an identity-only fast path.
    geometric: bool = True
    # Sub-block pixel-origin search step. Must stay 1: cropping shifts the block
    # grid by an arbitrary 0-7px, and a coarser step misses those offsets.
    pixel_step: int = 1

    @classmethod
    def full(cls) -> "SearchSpec":
        """Exhaustive search: the dense rotation/scale grid (for awkward distortions)."""
        return cls(scales=FULL_SCALES, angles=FULL_ANGLES, geometric=True, pixel_step=1)


def _geometries(search: SearchSpec) -> list[tuple[float, float]]:
    if search.geometric:
        return [(s, a) for s in search.scales for a in search.angles]
    return [(1.0, 0.0)]


# --------------------------------------------------------------------------- #
# Forensic mark (keyed, authenticated)
# --------------------------------------------------------------------------- #
def embed_image(
    image_rgb: np.ndarray,
    recipient_id: str,
    master_key: bytes,
    *,
    alpha: float = 7.0,
    contact: str | None = None,
) -> np.ndarray:
    """Embed the authenticated forensic mark for ``recipient_id``.

    If ``contact`` is given, also embed the public contact mark on a disjoint
    band (equivalent to calling :func:`embed_contact` afterwards).
    """
    sub = derive_subkeys(master_key)
    fbits = payload.bytes_to_bits(payload.encode_payload(recipient_id, sub.enc))
    cbits = (
        payload_public.bytes_to_bits(payload_public.encode_contact(contact))
        if contact is not None
        else None
    )

    def _mark(small: np.ndarray) -> np.ndarray:
        m = _embed.embed_bits(small, fbits, sub.prng, alpha=alpha, band=MID_BAND)
        if cbits is not None:
            m = _embed.embed_bits(m, cbits, PUBLIC_PRNG_KEY, alpha=alpha, band=MID_BAND_PUBLIC)
        return m

    return _normalized_embed(image_rgb, _mark)


def _search_decode(
    image_rgb: np.ndarray,
    plan,
    band: tuple[tuple[int, int], ...],
    decode_fn: Callable[[bytes], str],
    error_type: type[Exception],
    search: SearchSpec,
) -> str | None:
    """Generic blind search: geometry x pixel-origin x tile-offset, then decode.

    Returns the first successfully decoded payload, or None.
    """
    for scale, angle in _geometries(search):
        corrected = (
            image_rgb
            if (scale == 1.0 and angle == 0.0)
            else imageops.resample(image_rgb, scale=scale, angle=angle)
        )
        for sy in range(0, BLOCK, search.pixel_step):
            for sx in range(0, BLOCK, search.pixel_step):
                coeffs = _extract.block_coeffs(corrected, (sy, sx))
                votes, _ = _extract.best_offset_votes(coeffs, plan, band)
                cw = _bits_to_bytes(votes)
                try:
                    return decode_fn(cw)
                except error_type:
                    continue
    return None


def _bits_to_bytes(votes: np.ndarray) -> bytes:
    return np.packbits(_extract.votes_to_bits(votes)).tobytes()


def extract_image(
    image_rgb: np.ndarray,
    master_key: bytes,
    *,
    search: SearchSpec | None = None,
) -> str | None:
    """Blindly extract the recipient id, or ``None`` if no valid mark is found.

    A returned id is always GCM-authenticated, so a non-None result is never a
    forgery or a coincidence. The search tries the identity geometry first, so
    un-attacked images extract quickly.
    """
    search = search or SearchSpec()
    sub = derive_subkeys(master_key)
    plan = build_plan(sub.prng, payload.payload_bits(), len(MID_BAND))
    return _search_decode(
        _to_canonical(image_rgb), plan, MID_BAND,
        lambda cw: payload.decode_payload(cw, sub.enc),
        payload.PayloadError, search,
    )


# --------------------------------------------------------------------------- #
# Public contact mark (unencrypted, key-less)
# --------------------------------------------------------------------------- #
def embed_contact(image_rgb: np.ndarray, contact: str, *, alpha: float = 7.0) -> np.ndarray:
    """Embed the public, unencrypted contact mark on the public band."""
    bits = payload_public.bytes_to_bits(payload_public.encode_contact(contact))
    return _normalized_embed(
        image_rgb,
        lambda s: _embed.embed_bits(s, bits, PUBLIC_PRNG_KEY, alpha=alpha, band=MID_BAND_PUBLIC),
    )


def extract_contact(
    image_rgb: np.ndarray, *, search: SearchSpec | None = None
) -> str | None:
    """Blindly extract the public contact string (no key needed), or None."""
    search = search or SearchSpec()
    plan = build_plan(PUBLIC_PRNG_KEY, payload_public.payload_bits(), len(MID_BAND_PUBLIC))
    return _search_decode(
        _to_canonical(image_rgb), plan, MID_BAND_PUBLIC,
        payload_public.decode_contact, payload_public.PublicPayloadError, search,
    )


# --------------------------------------------------------------------------- #
# Diagnostics
# --------------------------------------------------------------------------- #
def recover_bits(
    image_rgb: np.ndarray,
    master_key: bytes,
    *,
    band: tuple[tuple[int, int], ...] = MID_BAND,
    n_bits: int | None = None,
    prng_key: bytes | None = None,
    search: SearchSpec | None = None,
) -> np.ndarray:
    """Blindly recover the raw payload bits at the max-energy synchronization.

    Unlike :func:`extract_image`, this does no payload decoding or
    authentication. Used to measure bit-error rate against a known embedded
    bitstream; it never returns an authenticated identifier.
    """
    search = search or SearchSpec()
    key = prng_key if prng_key is not None else derive_subkeys(master_key).prng
    bits = n_bits if n_bits is not None else payload.payload_bits()
    plan = build_plan(key, bits, len(band))
    image_rgb = _to_canonical(image_rgb)

    best_votes = np.zeros(plan.n_bits)
    best_score = -1.0
    for scale, angle in _geometries(search):
        corrected = (
            image_rgb
            if (scale == 1.0 and angle == 0.0)
            else imageops.resample(image_rgb, scale=scale, angle=angle)
        )
        for sy in range(0, BLOCK, search.pixel_step):
            for sx in range(0, BLOCK, search.pixel_step):
                coeffs = _extract.block_coeffs(corrected, (sy, sx))
                votes, score = _extract.best_offset_votes(coeffs, plan, band)
                if score > best_score:
                    best_score, best_votes = score, votes
    return _extract.votes_to_bits(best_votes)
