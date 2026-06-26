# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Measure watermark robustness: per-attack authenticated recovery + BER.

Recovery is the end-to-end authenticated extraction (the real metric). BER is
measured against a known random bitstream embedded through the same
scale-normalized pipeline, recovered with the default search.

    python tools/measure_robustness.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.attacks import ATTACKS  # noqa: E402
from tests.conftest import make_textured_image  # noqa: E402
from wmlib import api, embed, payload  # noqa: E402
from wmlib.keys import derive_subkeys  # noqa: E402
from wmlib.spread import build_plan  # noqa: E402

KEY = bytes.fromhex("ab" * 32)
ID = "banco-x-2026-05"


def main() -> None:
    # A realistic large scan, so messenger downscaling is meaningful.
    image = make_textured_image(1400, 2000)
    sub = derive_subkeys(KEY)

    bits = (
        np.random.default_rng(0)
        .integers(0, 2, size=payload.payload_bits())
        .astype(np.uint8)
    )
    plan = build_plan(sub.prng, payload.payload_bits())
    marked_bits = api._normalized_embed(
        image, lambda s: embed.embed_bits(s, bits, sub.prng, plan=plan)
    )
    marked_id = api.embed_image(image, ID, KEY)

    print(f"{'attack':<14} {'recovered?':<11} {'BER':>7}  {'bits ok':>8}")
    print("-" * 48)
    for name, attack in ATTACKS.items():
        t0 = time.time()
        recovered = api.extract_image(attack(marked_id), KEY)
        rec_bits = api.recover_bits(attack(marked_bits), KEY)
        ber = float(np.mean(rec_bits != bits))
        dt = time.time() - t0
        print(
            f"{name:<14} {('YES' if recovered == ID else 'no'):<11} "
            f"{ber:>7.4f}  {(1 - ber) * 100:>6.1f}%   ({dt:.1f}s)"
        )


if __name__ == "__main__":
    main()
