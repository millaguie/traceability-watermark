# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Tests for the legacy visible mosaic (deterrent only)."""

from __future__ import annotations

import fitz
import pytest
from PIL import Image, ImageChops

from wmlib import visible


@pytest.fixture
def sample_image(tmp_path):
    path = tmp_path / "doc.png"
    Image.new("RGB", (400, 300), (255, 255, 255)).save(path)
    return str(path)


@pytest.fixture
def sample_pdf(tmp_path):
    path = tmp_path / "doc.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "ORIGINAL DOCUMENT TEXT", fontsize=14)
    doc.save(str(path))
    doc.close()
    return str(path)


def test_overlay_is_semi_transparent_not_opaque():
    overlay = visible.make_watermark_overlay(400, 300, "SAMPLE", opacity=0.18)
    lo, hi = overlay.getchannel("A").getextrema()
    assert lo == 0 and 0 < hi < 255


def test_image_marked_but_readable(sample_image, tmp_path):
    out = str(tmp_path / "out.png")
    visible.watermark_image(sample_image, out, "Shared with Ana")
    diff = ImageChops.difference(
        Image.open(sample_image).convert("RGB"), Image.open(out).convert("RGB")
    ).convert("L")
    total = 400 * 300
    changed = total - diff.histogram()[0]
    assert 0 < changed < total * 0.5


def test_pdf_preserves_pages_and_text(sample_pdf, tmp_path):
    out = str(tmp_path / "out.pdf")
    visible.watermark_pdf(sample_pdf, out, "Shared with Ana")
    doc = fitz.open(out)
    try:
        assert doc.page_count == 1
        assert "ORIGINAL DOCUMENT TEXT" in doc[0].get_text()
        assert len(doc[0].get_images()) >= 1
    finally:
        doc.close()


def test_stamp_rejects_unsupported_format(tmp_path):
    bogus = tmp_path / "f.txt"
    bogus.write_text("hi")
    with pytest.raises(ValueError):
        visible.stamp(str(bogus), str(tmp_path / "o.txt"), "x")
