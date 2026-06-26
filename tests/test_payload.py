# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Tests for the authenticated, error-corrected payload codec.

Pipeline under test (no image involved here):
    recipient_id -> AES-256-GCM -> framed bytes -> Reed-Solomon codeword
and back, tolerating a bounded number of byte errors and rejecting any
tampering that GCM cannot authenticate.
"""

from __future__ import annotations

import pytest

from wmlib import payload

KEY = bytes.fromhex("ab" * 32)
KEY2 = bytes.fromhex("cd" * 32)


def test_round_trip_recovers_id():
    cw = payload.encode_payload("banco-x-2026-05", KEY)
    assert payload.decode_payload(cw, KEY) == "banco-x-2026-05"


def test_codeword_length_is_fixed_regardless_of_id():
    a = payload.encode_payload("a", KEY)
    b = payload.encode_payload("a-much-longer-recipient-id-here!", KEY)
    assert len(a) == len(b) == payload.codeword_length()


def test_nonce_randomized_but_both_decode():
    """Same id encodes to different bytes (random nonce) yet both decode."""
    c1 = payload.encode_payload("alice", KEY)
    c2 = payload.encode_payload("alice", KEY)
    assert c1 != c2
    assert payload.decode_payload(c1, KEY) == "alice"
    assert payload.decode_payload(c2, KEY) == "alice"


def test_wrong_key_is_rejected_not_garbage():
    cw = payload.encode_payload("alice", KEY)
    with pytest.raises(payload.PayloadError):
        payload.decode_payload(cw, KEY2)


def test_corrects_errors_within_rs_capacity():
    """Flipping up to parity/2 bytes is fully corrected."""
    cw = bytearray(payload.encode_payload("alice", KEY))
    correctable = payload.PARITY // 2
    for i in range(correctable):
        cw[i] ^= 0xFF
    assert payload.decode_payload(bytes(cw), KEY) == "alice"


def test_too_many_errors_raises_never_returns_wrong_id():
    """Beyond RS capacity it must raise, never silently return a wrong id."""
    cw = bytearray(payload.encode_payload("alice", KEY))
    for i in range(len(cw)):  # corrupt everything
        cw[i] ^= 0xFF
    with pytest.raises(payload.PayloadError):
        payload.decode_payload(bytes(cw), KEY)


def test_id_too_long_rejected():
    with pytest.raises(ValueError):
        payload.encode_payload("x" * (payload.MAX_ID_BYTES + 1), KEY)


def test_unicode_id_round_trip():
    ident = "José·María"  # multi-byte UTF-8, within byte budget
    assert payload.decode_payload(payload.encode_payload(ident, KEY), KEY) == ident


def test_to_bits_and_from_bits_round_trip():
    cw = payload.encode_payload("alice", KEY)
    bits = payload.bytes_to_bits(cw)
    assert set(bits.tolist()) <= {0, 1}
    assert len(bits) == len(cw) * 8
    assert payload.bits_to_bytes(bits) == cw
