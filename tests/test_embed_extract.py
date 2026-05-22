# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Clean round-trip and imperceptibility tests for the SS watermark core."""
from __future__ import annotations

import numpy as np
from skimage.metrics import structural_similarity as ssim

from wmlib import api, embed, extract, payload
from wmlib.keys import derive_subkeys
from wmlib.spread import build_plan

ID = "banco-x-2026-05"


def test_clean_round_trip_extracts_id(image, key):
    marked = api.embed_image(image, ID, key)
    assert api.extract_image(marked, key) == ID


def test_clean_bit_error_rate_is_zero(image, key):
    """With known bits and no attack, the matched filter must be error-free."""
    sub = derive_subkeys(key)
    n = payload.payload_bits()
    rng = np.random.default_rng(0)
    bits = rng.integers(0, 2, size=n).astype(np.uint8)
    plan = build_plan(sub.prng, n)

    marked = embed.embed_bits(image, bits, sub.prng, plan=plan)
    coeffs = extract.block_coeffs(marked)
    recovered = extract.votes_to_bits(extract.vote(coeffs, plan, (0, 0)))
    ber = float(np.mean(recovered != bits))
    assert ber == 0.0, f"clean BER should be 0, got {ber}"


def test_watermark_is_visually_imperceptible(image, key):
    marked = api.embed_image(image, ID, key)
    score = ssim(image, marked, channel_axis=-1)
    assert score >= 0.98, f"SSIM {score:.4f} below invisibility target 0.98"


def test_wrong_key_extracts_nothing(image, key):
    marked = api.embed_image(image, ID, key)
    other = bytes.fromhex("cd" * 32)
    # geometric=False keeps the (always-failing) negative search bounded/fast.
    assert api.extract_image(marked, other, search=api.SearchSpec(geometric=False)) is None


def test_no_watermark_extracts_nothing(image, key):
    assert api.extract_image(image, key, search=api.SearchSpec(geometric=False)) is None
