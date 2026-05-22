# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Robustness harness.

For each attack we assert TWO things:

  1. End-to-end authenticated recovery: ``extract_image`` returns the exact
     embedded id. This is the real security metric — a returned id is GCM-
     authenticated, so success means the bits survived *and* validated.
  2. Bit-error rate at the blind max-energy synchronization stays at/above the
     >=90%-bits-correct target from the design.

Honesty: thresholds are NOT tuned to pass. If an attack regresses below target,
this test fails and the number is reported rather than the threshold relaxed.

Geometric attacks need a rotation/scale resync search and are marked ``slow``;
run the fast subset with ``pytest -m "not slow"``.
"""
from __future__ import annotations

import numpy as np
import pytest

from wmlib import api, embed, payload
from wmlib.keys import derive_subkeys
from wmlib.spread import build_plan

from .attacks import (
    blur,
    crop,
    gaussian_noise,
    jpeg,
    messenger,
    rescale,
    rotate,
)

ID = "banco-x-2026-05"
BER_TARGET = 0.10  # >= 90% of bits correct after each individual attack

# (name, attack_fn, needs_geometric_search, marks)
CASES = [
    ("jpeg_q75", lambda im: jpeg(im, 75), False, ()),
    ("jpeg_q50", lambda im: jpeg(im, 50), False, ()),
    ("noise_sigma5", lambda im: gaussian_noise(im, 5.0), False, ()),
    ("blur_r1", lambda im: blur(im, 1.0), False, ()),
    ("crop_10pct", lambda im: crop(im, 0.10), False, ()),
    ("scale_0.8", lambda im: rescale(im, 0.8), True, (pytest.mark.slow,)),
    ("scale_1.2", lambda im: rescale(im, 1.2), True, (pytest.mark.slow,)),
    ("rotate_+2deg", lambda im: rotate(im, 2.0), True, (pytest.mark.slow,)),
    ("rotate_-2deg", lambda im: rotate(im, -2.0), True, (pytest.mark.slow,)),
]


def _blind_ber(attacked: np.ndarray, known_bits: np.ndarray, key: bytes, geometric: bool) -> float:
    spec = api.SearchSpec.full() if geometric else api.SearchSpec()
    recovered = api.recover_bits(attacked, key, search=spec)
    return float(np.mean(recovered != known_bits))


@pytest.mark.parametrize(
    "name,attack,geometric",
    [pytest.param(n, a, g, marks=m, id=n) for (n, a, g, m) in CASES],
)
def test_attack_recovers_and_meets_ber(name, attack, geometric, image, key):
    # Geometric attacks (rotate/scale) need the opt-in --full search; the rest
    # recover with the fast default.
    spec = api.SearchSpec.full() if geometric else api.SearchSpec()

    # 1. End-to-end authenticated recovery (the security-relevant metric).
    marked_id = api.embed_image(image, ID, key)
    recovered_id = api.extract_image(attack(marked_id), key, search=spec)
    assert recovered_id == ID, f"{name}: failed authenticated recovery"

    # 2. Bit-error rate against a known embedded bitstream.
    sub = derive_subkeys(key)
    n = payload.payload_bits()
    bits = np.random.default_rng(0).integers(0, 2, size=n).astype(np.uint8)
    plan = build_plan(sub.prng, n)
    # Embed the known bits through the same scale-normalized pipeline that
    # extraction undoes, so the BER is measured on a comparable signal.
    marked_bits = api._normalized_embed(
        image, lambda s: embed.embed_bits(s, bits, sub.prng, plan=plan)
    )

    ber = _blind_ber(attack(marked_bits), bits, key, geometric)
    assert ber <= BER_TARGET, f"{name}: BER {ber:.4f} exceeds target {BER_TARGET}"


@pytest.mark.parametrize("cap", [1280, 1024])
def test_survives_messenger_downscale(cap, key):
    """A large document sent 'as photo' (downscaled to a fixed cap + JPEG) by a
    messenger still yields the authenticated id, thanks to scale normalization."""
    from .conftest import make_textured_image

    big = make_textured_image(1400, 2000)  # realistic scan, > canonical
    marked = api.embed_image(big, ID, key)
    attacked = messenger(marked, long_side=cap, quality=85)
    assert api.extract_image(attacked, key) == ID
