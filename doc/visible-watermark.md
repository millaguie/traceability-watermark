# Visible watermarking (legacy mosaic — deterrent only)

## What it is

A **visible watermark** is an overlay that is intentionally perceptible — a
logo, a name, or a tiled text pattern blended over the content. Its purpose is
*deterrence and attribution*, not covert tracing: it discourages casual misuse
and signals ownership, while keeping the document legible. The classic technique
is alpha blending: `out = (1−α)·base + α·mark`, with a low `α` so the underlying
content stays readable.

Crucially, a visible overlay is **reversible**. Because the blend is linear and
the overlaid text is known (it is printed for the viewer to read), and on PDFs
the overlay is a separable image layer, the original can be recovered — by layer
deletion (PDF) or by subtracting the known pattern (image). It is therefore a
**deterrent, not a security control**.

## How this project uses it

[`visible.py`](../wmlib/visible.py) provides the legacy `--visible` mode:

- `make_watermark_overlay` builds a transparent RGBA layer with the text tiled
  diagonally (brick-offset rows), rotated, at low opacity (`0.18`), then
  `Image.alpha_composite`s it over the image; for PDFs the same overlay is
  inserted per page (the original text is preserved).
- `add_notice` draws the discreet "traceability-protected / if found, contact …"
  footer used alongside the *invisible* marks (see the top-level README and
  [payload-format](payload-format.md)).

The CLI and docs label this mode plainly as **deterrent only / reversible**, and
steer users to the invisible forensic mark for tamper resistance.

## Trade-offs

- Pros: instantly human-visible, zero-key, communicates intent, trivially cheap.
- Cons: reversible; degrades legibility somewhat; offers no real traceability
  against a motivated actor. It complements — never replaces — the invisible
  mark.

## References

- G. W. Braudaway, K. A. Magerlein, F. C. Mintzer, "Protecting publicly
  available images with a visible image watermark", *Proc. SPIE 2659, Optical
  Security and Counterfeit Deterrence Techniques*, 1996.
  https://doi.org/10.1117/12.235469
- S. P. Mohanty, K. R. Ramakrishnan, M. S. Kankanhalli, "A dual watermarking
  technique for images", *Proc. ACM Multimedia (Part 2)*, 1999.
  https://doi.org/10.1145/319878.319891
- Y. Hu, S. Kwong, "Wavelet domain adaptive visible watermarking", *Electronics
  Letters*, 37(20), 2001. https://doi.org/10.1049/el:20010838
