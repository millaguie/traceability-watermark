# PDF handling by flattening

## What it is

A PDF is a structured document (vector text, fonts, images, layers), not a
raster. There are two ways to watermark one:

- **Overlay**: add a new content layer (text or image) on top of the page,
  leaving the original objects intact underneath.
- **Flatten / rasterize**: render each page to a single raster image and rebuild
  the PDF from those images.

For *traceability* the overlay approach is fatally weak: the original page
objects remain untouched beneath the overlay, so an attacker simply deletes the
added layer (or extracts the still-intact text) and the mark is gone. This is
exactly the reversibility a forensic mark must avoid.

## How this project uses it

[`pdf.py`](../wmlib/pdf.py) **flattens** for the robust mark:

1. Render each page to an RGB raster at a chosen DPI (`get_pixmap`, PyMuPDF).
2. Embed the invisible forensic (and optional public contact) mark into that
   raster with the image pipeline ([spread-spectrum](spread-spectrum.md)).
3. Rebuild the output PDF with each page as the marked image.

There is **no separable original layer** to strip — the mark is now part of the
page pixels.

Two practical details:

- **Trade-off — searchable text is lost.** Flattening turns text into pixels, so
  the output is no longer selectable/searchable. That is the deliberate price of
  leaving nothing to peel off. (The legacy [visible](visible-watermark.md) mode
  keeps text because it is only a deterrent.)
- **DPI consistency.** Embed and extract must rasterize at the same DPI — a DPI
  mismatch is a large scale change that the bounded resync
  ([geometric-synchronization](geometric-synchronization.md)) won't undo. Both
  default to 200.
- The **visible notice** is drawn as real **vector text** on top
  (`_draw_notice`), not rasterized into the page, so it stays crisp at any zoom
  — that layer is public and meant to be seen, so a separate layer is fine.

## Trade-offs

- Flattening maximizes mark-removal resistance but sacrifices text and increases
  file size. For documents where searchable text must be preserved, only the
  (reversible) visible deterrent is appropriate.
- Rendering is library-dependent; PyMuPDF (AGPL) is used for fidelity and speed.

## References

- Adobe Systems, *PDF Reference / ISO 32000-1:2008, Document management —
  Portable document format*. https://www.iso.org/standard/51502.html
- PyMuPDF (rasterization/rebuild used here): https://pymupdf.readthedocs.io/
- General context: I. J. Cox et al., *Digital Watermarking and Steganography*,
  2nd ed., 2008 (document and print-domain watermarking).
