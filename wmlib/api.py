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

# Geometric *corrections* tried during blind detection; they invert the bounded
# attacks in the threat model (scale +-20%, rotation +-2deg). The FAST grid only
# tries the boundary corrections (cheap, covers the documented attack envelope);
# the FULL grid samples intermediate values for marginal/odd distortions.
FAST_SCALES: tuple[float, ...] = (1.0, 1.25, 0.8333)
FAST_ANGLES: tuple[float, ...] = (0.0, -2.0, 2.0)
FULL_SCALES: tuple[float, ...] = (1.0, 1.25, 0.8333, 1.111, 0.9)
FULL_ANGLES: tuple[float, ...] = (0.0, -1.0, 1.0, -2.0, 2.0)

# Fixed, published PRNG key for the public contact channel: it carries no
# secret, so anyone with the tool can locate and read it.
PUBLIC_PRNG_KEY = hashlib.sha256(b"watermark/public/v1").digest()


@dataclass
class SearchSpec:
    """Resynchronization search space for extraction.

    Defaults to a fast search (boundary geometries, every other pixel origin),
    which covers the documented attack envelope cheaply. :meth:`full` returns
    the exhaustive search for the rare case the fast one misses a mark.
    """

    scales: tuple[float, ...] = FULL_SCALES
    angles: tuple[float, ...] = FULL_ANGLES
    # Rotation/scale resync is expensive; OFF by default. The default still
    # recovers no-attack, JPEG, cropping, noise, blur and un-rotated screenshots
    # (those need only translation sync). Turn it ON for rotated/rescaled copies.
    geometric: bool = False
    # Sub-block pixel-origin search step. Must stay 1: cropping shifts the block
    # grid by an arbitrary 0-7px, and a coarser step misses those offsets.
    pixel_step: int = 1

    @classmethod
    def full(cls) -> "SearchSpec":
        """Exhaustive search incl. rotation/scale resync (slow; for distorted copies)."""
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
    codeword = payload.encode_payload(recipient_id, sub.enc)
    bits = payload.bytes_to_bits(codeword)
    marked = _embed.embed_bits(image_rgb, bits, sub.prng, alpha=alpha, band=MID_BAND)
    if contact is not None:
        marked = embed_contact(marked, contact, alpha=alpha)
    return marked


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
        image_rgb, plan, MID_BAND,
        lambda cw: payload.decode_payload(cw, sub.enc),
        payload.PayloadError, search,
    )


# --------------------------------------------------------------------------- #
# Public contact mark (unencrypted, key-less)
# --------------------------------------------------------------------------- #
def embed_contact(image_rgb: np.ndarray, contact: str, *, alpha: float = 7.0) -> np.ndarray:
    """Embed the public, unencrypted contact mark on the public band."""
    cw = payload_public.encode_contact(contact)
    bits = payload_public.bytes_to_bits(cw)
    return _embed.embed_bits(
        image_rgb, bits, PUBLIC_PRNG_KEY, alpha=alpha, band=MID_BAND_PUBLIC
    )


def extract_contact(
    image_rgb: np.ndarray, *, search: SearchSpec | None = None
) -> str | None:
    """Blindly extract the public contact string (no key needed), or None."""
    search = search or SearchSpec()
    plan = build_plan(PUBLIC_PRNG_KEY, payload_public.payload_bits(), len(MID_BAND_PUBLIC))
    return _search_decode(
        image_rgb, plan, MID_BAND_PUBLIC,
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
