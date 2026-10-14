#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Entry point for the traceability watermark tool.

Delegates to the subcommand CLI in :mod:`wmlib.cli`:

    python watermark.py embed   in.png  --id "banco-x"      # robust, invisible
    python watermark.py extract in.png                      # print recipient id
    python watermark.py verify  in.png --id "banco-x"
    python watermark.py embed   in.png  --visible --text "" # legacy deterrent

The legacy visible-mosaic helpers are re-exported here for backwards
compatibility with existing imports.
"""

from __future__ import annotations

from wmlib.cli import main
from wmlib.visible import (  # noqa: F401 - re-exported for compatibility
    make_watermark_overlay,
    stamp,
    watermark_image,
    watermark_pdf,
)

if __name__ == "__main__":
    raise SystemExit(main())
