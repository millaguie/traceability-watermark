# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Legacy *visible* watermark: a tiled, diagonal, semi-transparent text mosaic.

DETERRENT ONLY — NOT a security control. The original document is left intact
under a separate, partially transparent overlay. As a security analysis showed,
this is reversible: in PDFs the overlay image can be deleted to recover the
untouched page; in images the linear blend can be subtracted because the
recipient knows the overlaid text. Use it to discourage casual misuse and to
make sharing visibly attributed, not to resist a motivated attacker.

For traceability that resists removal, use the robust invisible mark
(:mod:`wmlib.api` / ``embed`` without ``--visible``).
"""

from __future__ import annotations

import io
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Image extensions handled directly by Pillow.
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
DEFAULT_DPI = 150


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a scalable TrueType font, trying several candidates per OS."""
    candidates = [
        "DejaVuSans-Bold.ttf",  # ships with Pillow
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_watermark_overlay(
    width: int,
    height: int,
    text: str,
    *,
    opacity: float = 0.18,
    angle: float = 30.0,
    font_scale: float = 0.022,
    color: tuple[int, int, int] = (255, 0, 0),
) -> Image.Image:
    """Build a transparent RGBA layer with the text as a diagonal mosaic."""
    font_size = max(12, int(min(width, height) * font_scale))
    font = _load_font(font_size)

    alpha = max(0, min(255, int(opacity * 255)))
    fill = (*color, alpha)

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = measure.textbbox((0, 0), text, font=font)
    text_w = int(bbox[2] - bbox[0])
    text_h = int(bbox[3] - bbox[1])

    step_x = text_w + int(font_size * 2.5)
    step_y = text_h + int(font_size * 3.5)

    diag = int(math.hypot(width, height)) + max(step_x, step_y)
    tile = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(tile)

    y, row = 0, 0
    while y < diag:
        x_offset = (step_x // 2) if (row % 2) else 0
        x = -step_x + x_offset
        while x < diag:
            tdraw.text((x, y), text, font=font, fill=fill)
            x += step_x
        y += step_y
        row += 1

    rotated = tile.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
    left = (rotated.width - width) // 2
    top = (rotated.height - height) // 2
    return rotated.crop((left, top, left + width, top + height))


def add_notice(
    image_rgb: np.ndarray,
    text: str,
    *,
    position: str = "bottom",
    opacity: float = 0.55,
    bg_opacity: float = 0.45,
) -> np.ndarray:
    """Draw a discreet, human-readable notice bar on a uint8 RGB array.

    Used for the public "this document is traceability-protected; if found,
    contact ..." footer. Returns a new RGB array of the same size.
    """
    img = Image.fromarray(image_rgb).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(11, int(w * 0.018))
    font = _load_font(font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(font_size * 0.6)
    band_h = th + 2 * pad
    y0 = (h - band_h) if position == "bottom" else 0

    # Translucent backing band for legibility over any content.
    draw.rectangle([0, y0, w, y0 + band_h], fill=(0, 0, 0, int(bg_opacity * 255)))
    draw.text(
        ((w - tw) // 2, y0 + pad - bbox[1]),
        text,
        font=font,
        fill=(255, 255, 255, int(opacity * 255 + 0.5 * 255)),
    )
    return np.asarray(Image.alpha_composite(img, overlay).convert("RGB"))


def watermark_image(input_path: str, output_path: str, text: str, **kw) -> None:
    """Apply the visible mosaic to an image and save it."""
    base = Image.open(input_path).convert("RGBA")
    overlay = make_watermark_overlay(base.width, base.height, text, **kw)
    combined = Image.alpha_composite(base, overlay)
    ext = os.path.splitext(output_path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        combined.convert("RGB").save(output_path, quality=95)
    else:
        combined.save(output_path)


def watermark_pdf(
    input_path: str, output_path: str, text: str, *, dpi: int = DEFAULT_DPI, **kw
) -> None:
    """Apply the visible mosaic to every PDF page (original text preserved)."""
    import fitz  # PyMuPDF; deferred import so image-only use needn't have it.

    doc = fitz.open(input_path)
    zoom = dpi / 72.0
    for page in doc:
        rect = page.rect
        px_w = max(1, int(rect.width * zoom))
        px_h = max(1, int(rect.height * zoom))
        overlay = make_watermark_overlay(px_w, px_h, text, **kw)
        buf = io.BytesIO()
        overlay.save(buf, format="PNG")
        page.insert_image(rect, stream=buf.getvalue(), overlay=True)
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()


def stamp(input_path: str, output_path: str, text: str, **kw) -> str:
    """Dispatch the visible mosaic by file extension. Returns ``output_path``."""
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".pdf":
        watermark_pdf(input_path, output_path, text, **kw)
    elif ext in IMAGE_EXTS:
        kw.pop("dpi", None)
        watermark_image(input_path, output_path, text, **kw)
    else:
        raise ValueError(f"Unsupported format: {ext}")
    return output_path
