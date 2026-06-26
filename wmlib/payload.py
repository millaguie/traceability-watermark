# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Authenticated, error-corrected payload codec.

Turns a short recipient identifier into a fixed-length byte codeword ready to
be embedded, and back. The pipeline is:

    recipient_id (<= MAX_ID_BYTES UTF-8)
        -> length-prefixed, zero-padded plaintext block
        -> AES-256-GCM (random nonce)            # confidentiality + integrity
        -> framed bytes (version | nonce | ct)
        -> Reed-Solomon codeword (adds PARITY bytes)

Decoding reverses this. Reed-Solomon repairs a bounded number of byte errors;
AES-GCM then authenticates, so any tampering RS cannot repair (or a wrong key)
is *rejected* rather than returning a forged or garbage identifier.

The fixed codeword length lets the embedding layer repeat a constant-size code
across the document, which is what makes cropping survivable.
"""

from __future__ import annotations

import os

import numpy as np
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from reedsolo import RSCodec, ReedSolomonError

VERSION = 1
MAX_ID_BYTES = 32  # recipient id capacity, in UTF-8 bytes
NONCE_BYTES = 12  # AES-GCM standard nonce
GCM_TAG_BYTES = 16
PARITY = 32  # Reed-Solomon parity bytes; corrects up to PARITY/2 byte errors

_LEN_PREFIX = 1
_PLAINTEXT_BLOCK = _LEN_PREFIX + MAX_ID_BYTES  # fixed-size plaintext
# version(1) + nonce + ciphertext(plaintext block + GCM tag)
_FRAMED_LEN = 1 + NONCE_BYTES + _PLAINTEXT_BLOCK + GCM_TAG_BYTES

_rs = RSCodec(PARITY)


class PayloadError(Exception):
    """Raised when a payload cannot be authenticated/decoded."""


def codeword_length() -> int:
    """Total codeword length in bytes (framed payload + RS parity)."""
    return _FRAMED_LEN + PARITY


def payload_bits() -> int:
    """Total codeword length in bits."""
    return codeword_length() * 8


def encode_payload(recipient_id: str, enc_key: bytes) -> bytes:
    """Encode ``recipient_id`` into a fixed-length authenticated codeword.

    Args:
        recipient_id: short identifier, at most ``MAX_ID_BYTES`` UTF-8 bytes.
        enc_key: 32-byte AES-256-GCM key (the derived ``enc`` subkey).

    Raises:
        ValueError: if the identifier exceeds the byte budget.
    """
    raw = recipient_id.encode("utf-8")
    if len(raw) > MAX_ID_BYTES:
        raise ValueError(f"recipient id is {len(raw)} bytes; max is {MAX_ID_BYTES}")

    block = bytes([len(raw)]) + raw + b"\x00" * (MAX_ID_BYTES - len(raw))
    nonce = os.urandom(NONCE_BYTES)
    ct = AESGCM(enc_key).encrypt(nonce, block, None)  # ct includes the 16B tag
    framed = bytes([VERSION]) + nonce + ct
    assert len(framed) == _FRAMED_LEN
    return bytes(_rs.encode(framed))


def decode_payload(codeword: bytes, enc_key: bytes) -> str:
    """Decode and authenticate a codeword back into the recipient id.

    Raises:
        PayloadError: if the codeword has too many errors, fails GCM
            authentication, was made with a different key, or is malformed.
    """
    try:
        framed = bytes(_rs.decode(bytes(codeword))[0])
    except ReedSolomonError as exc:
        raise PayloadError("too many errors to correct") from exc

    if len(framed) != _FRAMED_LEN or framed[0] != VERSION:
        raise PayloadError("unsupported or corrupt payload frame")

    nonce = framed[1 : 1 + NONCE_BYTES]
    ct = framed[1 + NONCE_BYTES :]
    try:
        block = AESGCM(enc_key).decrypt(nonce, ct, None)
    except InvalidTag as exc:
        raise PayloadError("authentication failed (wrong key or tampered)") from exc

    length = block[0]
    if length > MAX_ID_BYTES:
        raise PayloadError("invalid length prefix")
    return block[1 : 1 + length].decode("utf-8")


def bytes_to_bits(data: bytes) -> np.ndarray:
    """Expand bytes into a flat array of bits (MSB first), dtype uint8."""
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def bits_to_bytes(bits: np.ndarray) -> bytes:
    """Pack a flat 0/1 bit array (MSB first) back into bytes."""
    return np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes()
