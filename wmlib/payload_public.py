# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Public (unencrypted) contact payload codec.

Carries a human-meaningful "if found, contact ..." string that ANYONE with the
tool can read — no secret key. It is the invisible counterpart to the visible
contact notice, and survives attacks that crop the visible footer away.

Pipeline:

    contact string (<= MAX_CONTACT_BYTES UTF-8)
        -> magic | version | length | padded contact | CRC32
        -> Reed-Solomon codeword (fixed length)

There is deliberately NO authentication: the data is meant to be public. The
CRC + magic only guard against decoding noise into a bogus string when no mark
is present. Do not trust this payload for anything security-relevant; the keyed
forensic mark (:mod:`wmlib.payload`) is the trustworthy channel.
"""
from __future__ import annotations

import zlib

import numpy as np
from reedsolo import RSCodec, ReedSolomonError

MAGIC = b"WC"  # "watermark contact"
VERSION = 1
MAX_CONTACT_BYTES = 48
PARITY = 32  # Reed-Solomon parity bytes

_LEN = 1
_CRC = 4
_FRAME_LEN = len(MAGIC) + 1 + _LEN + MAX_CONTACT_BYTES + _CRC

_rs = RSCodec(PARITY)


class PublicPayloadError(Exception):
    """Raised when no valid public contact payload can be decoded."""


def codeword_length() -> int:
    """Total codeword length in bytes (framed payload + RS parity)."""
    return _FRAME_LEN + PARITY


def payload_bits() -> int:
    """Total codeword length in bits."""
    return codeword_length() * 8


def encode_contact(contact: str) -> bytes:
    """Encode ``contact`` into a fixed-length, CRC-protected codeword."""
    raw = contact.encode("utf-8")
    if len(raw) > MAX_CONTACT_BYTES:
        raise ValueError(f"contact is {len(raw)} bytes; max is {MAX_CONTACT_BYTES}")

    body = (
        MAGIC
        + bytes([VERSION, len(raw)])
        + raw
        + b"\x00" * (MAX_CONTACT_BYTES - len(raw))
    )
    frame = body + zlib.crc32(body).to_bytes(4, "big")
    assert len(frame) == _FRAME_LEN
    return bytes(_rs.encode(frame))


def decode_contact(codeword: bytes) -> str:
    """Decode and CRC-check a codeword back into the contact string."""
    try:
        frame = bytes(_rs.decode(bytes(codeword))[0])
    except ReedSolomonError as exc:
        raise PublicPayloadError("too many errors to correct") from exc

    if len(frame) != _FRAME_LEN or frame[: len(MAGIC)] != MAGIC or frame[2] != VERSION:
        raise PublicPayloadError("not a public contact payload")

    body, crc = frame[:-_CRC], int.from_bytes(frame[-_CRC:], "big")
    if zlib.crc32(body) != crc:
        raise PublicPayloadError("CRC mismatch (no valid mark present)")

    length = frame[3]
    if length > MAX_CONTACT_BYTES:
        raise PublicPayloadError("invalid length prefix")
    return frame[4 : 4 + length].decode("utf-8")


def bytes_to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def bits_to_bytes(bits: np.ndarray) -> bytes:
    return np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes()
