# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Tests for robust PDF embedding via flattening."""
from __future__ import annotations

import fitz
import pytest

from wmlib import pdf

KEY = bytes.fromhex("ab" * 32)
ID = "banco-x-2026-05"


@pytest.fixture
def text_pdf(tmp_path):
    """A one-page PDF large enough to carry the watermark, with real text."""
    path = tmp_path / "in.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # US Letter
    page.insert_text((72, 100), "ORIGINAL SELECTABLE TEXT", fontsize=18)
    doc.save(str(path))
    doc.close()
    return str(path)


def test_embed_then_extract_recovers_id(text_pdf, tmp_path):
    # Embedding and extraction must rasterize at the same DPI (the mark only
    # tolerates +-20% scale; a DPI mismatch is a larger scale change).
    out = str(tmp_path / "out.pdf")
    from wmlib.api import SearchSpec

    pdf.embed_pdf(text_pdf, out, ID, KEY, dpi=150)
    assert pdf.extract_pdf(out, KEY, dpi=150, search=SearchSpec(geometric=False)) == [ID]


def test_flattening_drops_selectable_text(text_pdf, tmp_path):
    """Documented trade-off: the original text is no longer extractable."""
    out = str(tmp_path / "out.pdf")
    pdf.embed_pdf(text_pdf, out, ID, KEY, dpi=150)
    doc = fitz.open(out)
    try:
        assert doc[0].get_text().strip() == ""  # page is now an image
    finally:
        doc.close()
