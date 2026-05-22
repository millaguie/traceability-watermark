# Traceability Watermark

Embed a per-recipient identifier into an image or PDF so that, if a shared copy
of a sensitive document (an ID card, a contract) later turns up in a leak, you
can trace which recipient it came from.

Three independent marks:

| Mark | How | Visible? | Who can read it | Trust |
| --- | --- | --- | --- | --- |
| **Forensic** (default) | invisible, keyed | No | only the owner (secret key) | Authenticated — identifies the recipient |
| **Public contact** | `--contact` | No (+ visible notice) | anyone with the tool, no key | Unauthenticated — "if found, contact ..." |
| **Visible mosaic** (legacy) | `--visible` | Yes | anyone | **Deterrent only — reversible** |

The forensic and public-contact marks live on **disjoint DCT bands**, so they
coexist in one image without interfering.

> The robust mark is a blind, spread-spectrum watermark in the DCT domain of the
> luminance channel, carrying an AES-256-GCM-encrypted payload protected by
> Reed–Solomon error correction.

## Install

### With pipx (recommended)

[pipx](https://pipx.pypa.io) installs the `watermark` command into its own
isolated environment, available system-wide:

```bash
pipx install traceability-watermark      # from PyPI (once published)
pipx install .                           # or from a local checkout
```

Then run it directly:

```bash
watermark embed dni.png --id "banco-x-2026-05"
```

Upgrade or remove:

```bash
pipx upgrade traceability-watermark
pipx uninstall traceability-watermark
```

### For development (editable + tests)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"     # editable install with test dependencies
```

## Usage

```bash
# Embed an invisible, traceable mark for a recipient
watermark embed dni.png   --id "banco-x-2026-05"
watermark embed dni.pdf   --id "banco-x-2026-05"     # flattens the PDF (see below)

# Stamp a visible "traceability-protected" warning (otherwise the mark is fully invisible)
watermark embed dni.png   --id "banco-x-2026-05" --notice

# Also add a public "if found, contact me" mark (+ visible footer notice)
watermark embed dni.png   --id "banco-x-2026-05" --contact "owner@example.com"

# Localize the visible notice (default English)
watermark embed dni.png   --id "banco-x-2026-05" --contact "owner@example.com" --lang es_ES

# Recover the recipient id from a (possibly attacked) copy
watermark extract leaked.jpg            # fast search (JPEG, crop, noise, blur...)
watermark extract leaked.jpg --full     # also undo rotation/scale (slow) if the above finds nothing

# Read ONLY the public contact mark — no key required (for a finder)
watermark contact leaked.jpg            # prints: owner@example.com

# Check whether a specific recipient's mark is present (exit 0 = yes)
watermark verify leaked.jpg --id "banco-x-2026-05"

# Legacy visible mosaic (deterrent only)
watermark embed dni.png --visible --text "Shared with Bank X"
```

`extract`/`verify`/`contact` use a fast search by default (recovers JPEG,
cropping, noise, blur, un-rotated screenshots). If that finds nothing and the
copy may have been **rotated or rescaled**, add `--full` to also search
rotation/scale (much slower).

## Public contact mark ("if found, contact ...")

`--contact` adds a second, **unencrypted** mark so that whoever ends up with a
copy can reach the owner, even though they can't read the encrypted recipient
id. It is embedded two ways at once:

- a **visible footer notice** (e.g. *"Traceability-protected document — if
  found, contact: owner@example.com"*), which a normal person can read at a
  glance; customize it with `--notice-text`, or suppress it with `--no-notice`.
  Use `--notice` alone (without `--contact`) to stamp just the
  "traceability-protected" warning — by default `embed` is fully invisible and
  shows nothing;
- an **invisible** copy on a separate DCT band, readable with `watermark
  contact` (no key) and surviving attacks that crop the visible footer away.

Caveats — by design this mark is **public**:

- it is **not authenticated**: anyone can read, strip or overwrite it, so don't
  rely on it for anything you must trust (that's what the keyed forensic mark is
  for);
- the contact info is **exposed in any leak**. Use a dedicated alias/inbox, not
  a private personal address;
- it also serves as **transparency/deterrence**: it tells holders the document
  is traceability-protected (sensible for GDPR-style notice and to discourage
  misuse).

## Threat model

The robust mark is designed to survive a **technical recipient** who has the
file, knows a watermark exists, and tries to remove it before leaking, within
these bounds:

- JPEG recompression (quality ≥ 50)
- rescaling ±20%
- cropping ≤ 10% per edge
- rotation ±2°
- additive noise / mild blur

Measured robustness on a textured test image (see `tools/measure_robustness.py`
and `tests/test_robustness.py`): **all of the above recover the authenticated
id**, with ≥ 99.6 % of payload bits correct per individual attack (worst case
JPEG q=50). High-key documents (mostly-white scans) are handled by reserving
luminance headroom before embedding; see the limitation note below.

## What it does and does NOT guarantee

**It guarantees** (within the bounds above):

- *Blind detection* — no original document needed.
- *Authenticity* — a recovered id is AES-GCM-authenticated; the tool never
  returns a forged or coincidental id. Without the secret key an attacker
  cannot read or forge identifiers.

**It does NOT guarantee irreversibility.** No watermark resists an attacker with
unlimited resources. Known limitations, stated plainly:

- **Collusion**: averaging several copies carrying *different* ids can wash out
  or confuse the mark.
- **Reconstruction from scratch**: OCR + retyping, or re-creating the document,
  removes any signal.
- **Out-of-bounds distortions**: aggressive scaling/rotation, large crops that
  remove all redundancy, heavy denoising or AI regeneration can defeat it.
- **High-key / near-blank documents**: pages that are almost entirely flat white
  carry little texture to hide signal in; robustness drops on such inputs.
- **Print → scan**: not in the tested bounds; expect degraded recovery.
- The **visible** mode is explicitly reversible and is a deterrent only.

## PDF handling (flattening)

The robust mark is **not** overlaid on top of intact page content (which an
attacker could simply delete). Instead each page is rasterized to an image, the
mark is embedded there, and the PDF is rebuilt from the marked images.

**Trade-off:** the original selectable/searchable text is lost — every page
becomes an image. That is the price of leaving no separable original layer
under the mark. (The legacy `--visible` mode keeps the text, because it is only
a deterrent.)

**DPI consistency:** `embed` and `extract` rasterize at `--dpi` (default 200).
Because the mark only tolerates ±20% scaling, you must extract at the **same
DPI used to embed**. Using the defaults for both keeps them consistent.

## Key management

The secret master key (256-bit) **never lives in code**. It is sourced, in
order, from:

1. `--key-file <path>` (hex),
2. the `WATERMARK_KEY` environment variable (hex),
3. `$XDG_CONFIG_HOME/watermark/key` (or `~/.config/watermark/key`).

If none exists, a key is generated and written to the config path with `0600`
permissions, and a notice is printed. **Back this key up**: without it you can
neither extract existing marks nor prove provenance. Two independent subkeys
(carrier PRNG and payload encryption) are derived from it via HKDF-SHA256.

## Tests

```bash
pytest -m "not slow"   # fast suite
pytest                 # full suite incl. geometric robustness (slower)
python tools/measure_robustness.py   # per-attack BER / recovery table
```

## License

Copyright (C) 2026 millaguie <https://www.millaguie.net/>

This program is free software: you can redistribute it and/or modify it under
the terms of the **GNU Affero General Public License v3.0 or later (AGPLv3+)**
as published by the Free Software Foundation. It is distributed WITHOUT ANY
WARRANTY. See the [LICENSE](LICENSE) file for the full text.

AGPL was chosen to match PyMuPDF (the PDF dependency), which is itself AGPL-3.0;
this keeps the whole stack under a single, consistent copyleft.
