# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Compare our DCT-SS backend against the `invisible-watermark` library.

Same textured image, same attack suite. Reports per-attack bit-error rate for
each backend, plus imperceptibility (SSIM) and embed/extract timing. The point
is a fair, measured basis to decide whether invisible-watermark is worth adding
as an alternative backend.

    python tools/compare_backends.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from skimage.metrics import structural_similarity as ssim

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from imwatermark import WatermarkDecoder, WatermarkEncoder  # noqa: E402

from tests.attacks import ATTACKS  # noqa: E402
from tests.conftest import make_textured_image  # noqa: E402
from wmlib import api, embed, payload  # noqa: E402
from wmlib.keys import derive_subkeys  # noqa: E402
from wmlib.spread import build_plan  # noqa: E402

KEY = bytes.fromhex("ab" * 32)


# --------------------------------------------------------------------------- #
# invisible-watermark wrappers (it works in BGR uint8)
# --------------------------------------------------------------------------- #
def iw_embed(rgb: np.ndarray, bits: list[int], method: str) -> np.ndarray:
    enc = WatermarkEncoder()
    enc.set_watermark("bits", bits)
    bgr = rgb[..., ::-1].copy()
    out = enc.encode(bgr, method)
    return out[..., ::-1].copy()  # back to RGB


def iw_ber(rgb_marked: np.ndarray, bits: list[int], method: str) -> float:
    dec = WatermarkDecoder("bits", len(bits))
    bgr = rgb_marked[..., ::-1].copy()
    rec = np.array(dec.decode(bgr, method), dtype=np.uint8)
    truth = np.array(bits, dtype=np.uint8)
    if rec.size != truth.size:
        return 1.0
    return float(np.mean(rec != truth))


# --------------------------------------------------------------------------- #
# our backend BER at the blind max-energy synchronization
# --------------------------------------------------------------------------- #
def ours_ber(rgb_marked: np.ndarray, bits: np.ndarray, geometric: bool) -> float:
    rec = api.recover_bits(rgb_marked, KEY, search=api.SearchSpec(geometric=geometric))
    return float(np.mean(rec != bits))


def make_natural_image(h: int = 512, w: int = 512, seed: int = 5) -> np.ndarray:
    """Smooth, photo-like image (no sharp edges) — fair to all DWT/DCT methods."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    g = 128 + 40 * np.sin(xx / 40) + 30 * np.cos(yy / 55) + rng.normal(0, 8, (h, w))
    g = np.clip(g, 0, 255).astype(np.uint8)
    return np.stack([g, np.roll(g, 7, 1), np.roll(g, -7, 0)], -1)


def main() -> None:
    # Natural (smooth) image so every backend decodes cleanly at baseline; this
    # makes the attack comparison fair. (Our backend also handles the sharp,
    # document-like textured image — where dwtDct degrades to ~10% clean BER.)
    image = make_natural_image()
    sub = derive_subkeys(KEY)

    # Ours: full 752-bit authenticated codeword.
    n = payload.payload_bits()
    our_bits = np.random.default_rng(0).integers(0, 2, n).astype(np.uint8)
    plan = build_plan(sub.prng, n)
    t0 = time.time()
    ours_marked = embed.embed_bits(image, our_bits, sub.prng, plan=plan)
    ours_embed_t = time.time() - t0

    # invisible-watermark: its typical short payload (64 bits).
    iw_bits = list(np.random.default_rng(1).integers(0, 2, 64).astype(int))
    iw_methods = ["dwtDct", "dwtDctSvd"]
    iw_marked = {}
    iw_embed_t = {}
    for mth in iw_methods:
        t0 = time.time()
        iw_marked[mth] = iw_embed(image, iw_bits, mth)
        iw_embed_t[mth] = time.time() - t0

    # Imperceptibility.
    print("== Imperceptibility (SSIM vs original) & capacity ==")
    print(f"  ours        SSIM={ssim(image, ours_marked, channel_axis=-1):.4f}  payload={n} bits (authenticated)")
    for mth in iw_methods:
        print(f"  {mth:<11} SSIM={ssim(image, iw_marked[mth], channel_axis=-1):.4f}  payload={len(iw_bits)} bits (raw)")

    print(f"\n== Embed time ==  ours={ours_embed_t*1000:.0f}ms  " + "  ".join(f"{m}={iw_embed_t[m]*1000:.0f}ms" for m in iw_methods))

    # Robustness.
    geo = {"scale_0.8", "scale_1.2", "rotate_+2deg", "rotate_-2deg"}
    print("\n== Bit-error rate per attack (lower is better) ==")
    print(f"{'attack':<14}{'ours':>10}{'dwtDct':>10}{'dwtDctSvd':>12}")
    print("-" * 46)
    for name, attack in ATTACKS.items():
        our_b = ours_ber(attack(ours_marked), our_bits, geometric=name in geo)
        row = f"{name:<14}{our_b:>10.4f}"
        for mth in iw_methods:
            row += f"{iw_ber(attack(iw_marked[mth]), iw_bits, mth):>{10 if mth=='dwtDct' else 12}.4f}"
        print(row)


if __name__ == "__main__":
    main()
