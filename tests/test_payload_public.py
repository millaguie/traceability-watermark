# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Tests for the public (unencrypted) contact payload codec.

This payload is intentionally readable WITHOUT any secret: anyone with the tool
can extract the contact info. A CRC + magic/version guards against returning
garbage when no mark is present (there is no authentication — by design).
"""

from __future__ import annotations

import pytest

from wmlib import payload_public as pp

CONTACT = "owner@example.com"


def test_round_trip():
    cw = pp.encode_contact(CONTACT)
    assert pp.decode_contact(cw) == CONTACT


def test_fixed_length_regardless_of_contact():
    a = pp.encode_contact("a@b.co")
    b = pp.encode_contact("a-much-longer-address@some-domain.example")
    assert len(a) == len(b) == pp.codeword_length()


def test_no_key_needed_deterministic():
    # Same input -> same codeword (no nonce/randomness): public + reproducible.
    assert pp.encode_contact(CONTACT) == pp.encode_contact(CONTACT)


def test_corrects_errors_within_rs_capacity():
    cw = bytearray(pp.encode_contact(CONTACT))
    for i in range(pp.PARITY // 2):
        cw[i] ^= 0xFF
    assert pp.decode_contact(bytes(cw)) == CONTACT


def test_garbage_rejected_by_crc():
    cw = bytearray(pp.encode_contact(CONTACT))
    for i in range(len(cw)):  # destroy everything
        cw[i] ^= 0xA5
    with pytest.raises(pp.PublicPayloadError):
        pp.decode_contact(bytes(cw))


def test_too_long_rejected():
    with pytest.raises(ValueError):
        pp.encode_contact("x" * (pp.MAX_CONTACT_BYTES + 1))


def test_unicode_contact():
    ident = "José ☎ +34·600"
    assert pp.decode_contact(pp.encode_contact(ident)) == ident
