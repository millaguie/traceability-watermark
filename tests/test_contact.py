# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Tests for the public contact mark and its coexistence with the forensic mark."""

from __future__ import annotations

from skimage.metrics import structural_similarity as ssim

from wmlib import api

from .attacks import jpeg
from .conftest import KEY

ID = "banco-x-2026-05"
CONTACT = "if-found@example.com"
FAST = api.SearchSpec(geometric=False)


def test_contact_round_trip_without_key(image):
    marked = api.embed_contact(image, CONTACT)
    # No key argument at all — the contact channel is public.
    assert api.extract_contact(marked, search=FAST) == CONTACT


def test_both_marks_coexist(image):
    """Forensic id and public contact must both survive in the same image."""
    marked = api.embed_image(image, ID, KEY, contact=CONTACT)
    assert api.extract_image(marked, KEY, search=FAST) == ID
    assert api.extract_contact(marked, search=FAST) == CONTACT


def test_contact_does_not_need_the_forensic_key(image):
    marked = api.embed_image(image, ID, KEY, contact=CONTACT)
    wrong = bytes.fromhex("cd" * 32)
    # Wrong key can't read the id, but the contact is still public.
    assert api.extract_image(marked, wrong, search=FAST) is None
    assert api.extract_contact(marked, search=FAST) == CONTACT


def test_no_contact_mark_extracts_none(image):
    marked = api.embed_image(image, ID, KEY)  # no contact embedded
    assert api.extract_contact(marked, search=FAST) is None


def test_contact_survives_jpeg(image):
    marked = api.embed_image(image, ID, KEY, contact=CONTACT)
    attacked = jpeg(marked, 75)
    assert api.extract_contact(attacked, search=FAST) == CONTACT
    assert api.extract_image(attacked, KEY, search=FAST) == ID


def test_dual_mark_stays_reasonably_invisible(image):
    # Two stacked marks roughly double the (small) perturbation, so the dual
    # target is slightly looser than the single-mark >=0.98.
    marked = api.embed_image(image, ID, KEY, contact=CONTACT)
    assert ssim(image, marked, channel_axis=-1) >= 0.96
