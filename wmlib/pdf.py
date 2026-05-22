# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""PDF support via flattening.

Unlike the legacy visible stamp, the robust watermark is *not* overlaid on top
of intact page content (which an attacker could simply delete). Instead each
page is rasterized to an image, the robust mark is embedded in that raster, and
the output PDF is rebuilt from the marked images.

Trade-off (documented for the user): the original selectable/searchable text is
lost — every page becomes an image. That is the price of leaving no separable
original layer underneath the mark.
"""
from __future__ import annotations

import io

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

from . import api

DEFAULT_DPI = 200


def _page_to_rgb(page: "fitz.Page", dpi: int) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return arr.copy()


def _draw_notice(page: "fitz.Page", text: str) -> None:
    """Draw the visible notice as crisp vector text (a translucent footer band).

    Unlike rasterizing it into the flattened page image, this stays sharp at any
    zoom. The notice is public, so a separate text layer is fine here.
    """
    rect = page.rect
    fontsize = max(7.0, rect.width * 0.016)
    band_h = fontsize * 2.2
    band = fitz.Rect(0, rect.height - band_h, rect.width, rect.height)

    shape = page.new_shape()
    shape.draw_rect(band)
    shape.finish(fill=(0, 0, 0), fill_opacity=0.5, width=0)
    shape.commit()

    page.insert_textbox(
        band, text, fontsize=fontsize, fontname="helv",
        color=(1, 1, 1), align=fitz.TEXT_ALIGN_CENTER,
    )


def embed_pdf(
    input_path: str,
    output_path: str,
    recipient_id: str,
    master_key: bytes,
    *,
    dpi: int = DEFAULT_DPI,
    alpha: float = 7.0,
    contact: str | None = None,
    notice: str | None = None,
) -> None:
    """Flatten each page, embed the robust watermark, and write a new PDF.

    If ``contact`` is given, also embed the public contact mark; if ``notice``
    is given, stamp a visible footer notice (as crisp vector text) on each page.
    """
    src = fitz.open(input_path)
    out = fitz.open()
    try:
        for page in src:
            rgb = _page_to_rgb(page, dpi)
            marked = api.embed_image(rgb, recipient_id, master_key, alpha=alpha, contact=contact)

            buf = io.BytesIO()
            Image.fromarray(marked).save(buf, format="PNG")
            new_page = out.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(page.rect, stream=buf.getvalue())
            if notice:
                _draw_notice(new_page, notice)
        out.save(output_path, garbage=4, deflate=True)
    finally:
        src.close()
        out.close()


def extract_pdf(
    input_path: str,
    master_key: bytes,
    *,
    dpi: int = DEFAULT_DPI,
    search: "api.SearchSpec | None" = None,
) -> list[str | None]:
    """Extract the recipient id from each page; entry is None if none found."""
    doc = fitz.open(input_path)
    try:
        results: list[str | None] = []
        for page in doc:
            rgb = _page_to_rgb(page, dpi)
            results.append(api.extract_image(rgb, master_key, search=search))
        return results
    finally:
        doc.close()


def extract_contact_pdf(
    input_path: str,
    *,
    dpi: int = DEFAULT_DPI,
    search: "api.SearchSpec | None" = None,
) -> list[str | None]:
    """Extract the public contact string from each page (no key needed)."""
    doc = fitz.open(input_path)
    try:
        return [api.extract_contact(_page_to_rgb(page, dpi), search=search) for page in doc]
    finally:
        doc.close()
