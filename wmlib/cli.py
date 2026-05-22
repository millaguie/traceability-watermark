# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Command-line interface: embed / extract / verify (+ legacy visible stamp).

    watermark embed  in.png  --id "banco-x"            # robust, invisible
    watermark embed  in.pdf  --id "banco-x"            # flattens the PDF
    watermark embed  in.png  --visible --text "..."    # legacy mosaic (deterrent)
    watermark extract in.png                           # prints the recipient id
    watermark verify  in.png --id "banco-x"            # exit 0 if it matches

The robust mark is invisible, keyed, authenticated and survives recompression,
mild scaling/rotation and cropping. The ``--visible`` mosaic is a DETERRENT
only and is reversible — see :mod:`wmlib.visible`.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from . import api, i18n, pdf, visible
from .imageops import load_rgb, save_rgb
from .keys import load_master_key

_DETERRENT_NOTE = (
    "NOTE: --visible is a DETERRENT ONLY, not a security control. It is "
    "reversible (the original is recoverable). For tamper-resistant "
    "traceability use the default invisible mark."
)


def _default_output(input_path: str, suffix: str = "_watermarked") -> str:
    root, ext = os.path.splitext(input_path)
    return f"{root}{suffix}{ext}"


def _is_pdf(path: str) -> bool:
    return os.path.splitext(path)[1].lower() == ".pdf"


def _cmd_embed(args) -> int:
    if not os.path.isfile(args.input):
        print(f"error: file not found: {args.input!r}", file=sys.stderr)
        return 1

    if args.visible:
        if not args.text:
            print("error: --visible requires --text", file=sys.stderr)
            return 1
        print(_DETERRENT_NOTE, file=sys.stderr)
        text = args.text if args.no_date else f"{args.text} · {date.today().isoformat()}"
        out = args.output or _default_output(args.input, "_stamped")
        visible.stamp(args.input, out, text)
        print(f"visible stamp applied -> {out}")
        return 0

    # Robust invisible mark.
    if not args.id:
        print("error: embed requires --id (or --visible --text)", file=sys.stderr)
        return 1
    key = load_master_key(key_file=args.key_file)
    out = args.output or _default_output(args.input)

    # Public contact mark (invisible) + visible notice.
    contact = args.contact
    if args.lang and not i18n.is_supported(args.lang):
        print(
            f"warning: notice language {args.lang!r} not available, using English. "
            f"Supported: {', '.join(i18n.available())}. Use --notice-text for others.",
            file=sys.stderr,
        )
    notice = None
    if args.no_notice:
        notice = None
    elif args.notice_text:
        notice = args.notice_text
    elif contact:
        notice = i18n.notice(args.lang, contact)
    elif args.notice:
        notice = i18n.notice(args.lang)

    if _is_pdf(args.input):
        print(
            "note: robust PDF embedding flattens pages to images; the original "
            "selectable text is lost (by design — no removable overlay).",
            file=sys.stderr,
        )
        pdf.embed_pdf(
            args.input, out, args.id, key,
            dpi=args.dpi, alpha=args.alpha, contact=contact, notice=notice,
        )
    else:
        marked = api.embed_image(load_rgb(args.input), args.id, key, alpha=args.alpha, contact=contact)
        if notice:
            marked = visible.add_notice(marked, notice)
        save_rgb(marked, out)

    extras = []
    if contact:
        extras.append("public contact mark")
    if notice:
        extras.append("visible notice")
    suffix = f" (+ {', '.join(extras)})" if extras else ""
    print(f"invisible mark embedded -> {out}{suffix}")
    return 0


def _search_spec(args) -> api.SearchSpec:
    # Default is the fast (non-geometric) search; --full adds rotation/scale resync.
    return api.SearchSpec.full() if getattr(args, "full", False) else api.SearchSpec()


def _cmd_extract(args) -> int:
    if not os.path.isfile(args.input):
        print(f"error: file not found: {args.input!r}", file=sys.stderr)
        return 1
    key = load_master_key(key_file=args.key_file)
    spec = _search_spec(args)

    if _is_pdf(args.input):
        results = pdf.extract_pdf(args.input, key, dpi=args.dpi, search=spec)
        found = False
        for i, rid in enumerate(results, 1):
            if rid is not None:
                print(f"page {i}: {rid}")
                found = True
        if not found:
            print("no valid watermark found", file=sys.stderr)
        return 0 if found else 1

    rgb = load_rgb(args.input)
    rid = api.extract_image(rgb, key, search=spec)
    contact = api.extract_contact(rgb, search=spec)
    if rid is None and contact is None:
        print("no valid watermark found", file=sys.stderr)
        return 1
    if rid is not None:
        print(rid)
    if contact is not None:
        print(f"contact: {contact}", file=sys.stderr)
    return 0 if rid is not None else 1


def _cmd_contact(args) -> int:
    """Read the public contact mark only — no key required."""
    if not os.path.isfile(args.input):
        print(f"error: file not found: {args.input!r}", file=sys.stderr)
        return 1
    spec = _search_spec(args)
    if _is_pdf(args.input):
        results = pdf.extract_contact_pdf(args.input, dpi=args.dpi, search=spec)
        found = False
        for i, c in enumerate(results, 1):
            if c is not None:
                print(f"page {i}: {c}")
                found = True
        if not found:
            print("no contact mark found", file=sys.stderr)
        return 0 if found else 1

    contact = api.extract_contact(load_rgb(args.input), search=spec)
    if contact is None:
        print("no contact mark found", file=sys.stderr)
        return 1
    print(contact)
    return 0


def _cmd_verify(args) -> int:
    if not os.path.isfile(args.input):
        print(f"error: file not found: {args.input!r}", file=sys.stderr)
        return 1
    key = load_master_key(key_file=args.key_file)
    spec = _search_spec(args)

    if _is_pdf(args.input):
        found = any(r == args.id for r in pdf.extract_pdf(args.input, key, dpi=args.dpi, search=spec))
    else:
        found = api.extract_image(load_rgb(args.input), key, search=spec) == args.id

    if found:
        print(f"MATCH: {args.id!r}")
        return 0
    print(f"NO MATCH for {args.id!r}", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="watermark",
        description="Robust, invisible, authenticated traceability watermark "
        "for images and PDFs (with a legacy visible-mosaic deterrent).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_key(sp):
        sp.add_argument(
            "--key-file",
            help="hex key file; else $WATERMARK_KEY, else ~/.config/watermark/key "
            "(auto-generated with 0600 if absent)",
        )

    e = sub.add_parser("embed", help="embed a watermark")
    e.add_argument("input", help="input image or PDF")
    e.add_argument("-o", "--output", help="output path (default: <name>_watermarked.<ext>)")
    e.add_argument("--id", help="recipient identifier for the robust invisible mark")
    e.add_argument("--alpha", type=float, default=7.0, help="embedding strength (default: 7.0)")
    e.add_argument("--dpi", type=int, default=pdf.DEFAULT_DPI, help="raster DPI for PDFs")
    e.add_argument(
        "--visible", action="store_true",
        help=f"use the legacy visible mosaic instead. {_DETERRENT_NOTE}",
    )
    e.add_argument("--text", help="text for --visible mode")
    e.add_argument("--no-date", action="store_true", help="(--visible) do not append today's date")
    e.add_argument(
        "--contact",
        help="public 'if found, contact' info (e.g. an email). Embedded as an "
        "unencrypted, key-less invisible mark plus a visible notice.",
    )
    e.add_argument(
        "--notice", action="store_true",
        help="stamp a visible 'traceability-protected document' notice (no contact needed)",
    )
    e.add_argument(
        "--lang", default="en",
        help=f"notice language (default en). Supported: {', '.join(i18n.available())}",
    )
    e.add_argument("--notice-text", help="custom visible notice text (also adds a visible notice)")
    e.add_argument("--no-notice", action="store_true", help="suppress the visible notice even with --contact")
    add_key(e)
    e.set_defaults(func=_cmd_embed)

    x = sub.add_parser("extract", help="extract the recipient id (blind)")
    x.add_argument("input", help="input image or PDF")
    x.add_argument("--dpi", type=int, default=pdf.DEFAULT_DPI, help="raster DPI for PDFs")
    x.add_argument(
        "--full", action="store_true",
        help="also search rotation/scale (slow); use if a plain extract finds "
        "nothing and the copy may have been rotated or rescaled",
    )
    add_key(x)
    x.set_defaults(func=_cmd_extract)

    v = sub.add_parser("verify", help="check whether a given id is present")
    v.add_argument("input", help="input image or PDF")
    v.add_argument("--id", required=True, help="recipient id to check for")
    v.add_argument("--dpi", type=int, default=pdf.DEFAULT_DPI, help="raster DPI for PDFs")
    v.add_argument("--full", action="store_true", help="also search rotation/scale (slow)")
    add_key(v)
    v.set_defaults(func=_cmd_verify)

    c = sub.add_parser("contact", help="read the public contact mark (no key needed)")
    c.add_argument("input", help="input image or PDF")
    c.add_argument("--dpi", type=int, default=pdf.DEFAULT_DPI, help="raster DPI for PDFs")
    c.add_argument("--full", action="store_true", help="also search rotation/scale (slow)")
    c.set_defaults(func=_cmd_contact)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - surface a clean message
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
