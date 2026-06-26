# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Secret key management for the robust watermark.

The master secret never lives in code. It is sourced, in order, from:

  1. an explicit key file (``--key-file`` / ``key_file`` argument),
  2. the ``WATERMARK_KEY`` environment variable (hex-encoded),
  3. a config file (default ``$XDG_CONFIG_HOME/watermark/key`` or
     ``~/.config/watermark/key``), created with ``0600`` permissions.

If none of these exist, a fresh 256-bit key is generated and persisted to the
config file so subsequent runs are reproducible.

Two independent subkeys are derived from the master with HKDF-SHA256:

  * ``prng`` — drives coefficient selection, PN sequences and tiling,
  * ``enc``  — the AES-256-GCM key protecting the payload.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_SIZE = 32  # 256 bits
ENV_VAR = "WATERMARK_KEY"

# HKDF domain-separation labels. Changing these invalidates existing marks.
_INFO_PRNG = b"watermark/v1/prng"
_INFO_ENC = b"watermark/v1/enc"


@dataclass(frozen=True)
class Subkeys:
    """Subkeys derived from the master secret."""

    prng: bytes
    enc: bytes


def generate_key() -> bytes:
    """Return a fresh cryptographically random 256-bit key."""
    return os.urandom(KEY_SIZE)


def default_key_path() -> Path:
    """Return the default config path for the persisted master key."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "watermark" / "key"


def _parse_key(text: str, *, source: str) -> bytes:
    """Decode a hex key string and validate its length."""
    cleaned = "".join(text.split())  # tolerate whitespace / trailing newline
    try:
        raw = bytes.fromhex(cleaned)
    except ValueError as exc:
        raise ValueError(f"{source}: key is not valid hex") from exc
    if len(raw) != KEY_SIZE:
        raise ValueError(
            f"{source}: key must be {KEY_SIZE} bytes ({KEY_SIZE * 2} hex chars), "
            f"got {len(raw)}"
        )
    return raw


def _persist_key(path: Path, key: bytes) -> None:
    """Write the key as hex to ``path`` with owner-only (0600) permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Create with restrictive perms from the start (avoid a readable window).
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, (key.hex() + "\n").encode("ascii"))
    finally:
        os.close(fd)
    os.chmod(path, 0o600)  # enforce even if the file pre-existed


def _warn_loose_permissions(path: Path) -> None:
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        print(
            f"warning: key file {path} is accessible by group/other "
            f"(mode {oct(mode)}); tighten with: chmod 600 {path}",
            file=sys.stderr,
        )


def load_master_key(
    key_file: str | os.PathLike[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    config_path: str | os.PathLike[str] | None = None,
    autogenerate: bool = True,
    warn: bool = True,
) -> bytes:
    """Load the 256-bit master key from the first available source.

    Args:
        key_file: explicit hex key file; highest precedence.
        env: environment mapping to read ``WATERMARK_KEY`` from (defaults to
            ``os.environ``). Pass ``{}`` in tests to ignore the real env.
        config_path: where the persisted key lives (defaults to
            :func:`default_key_path`).
        autogenerate: if no source has a key, generate and persist one.
        warn: emit a stderr warning on auto-generation or loose permissions.

    Returns:
        The 32-byte master key.

    Raises:
        ValueError: if a provided key is malformed or the wrong length.
        FileNotFoundError: if no key is found and ``autogenerate`` is False.
    """
    environ: Mapping[str, str] = os.environ if env is None else env
    cfg = Path(config_path) if config_path is not None else default_key_path()

    # 1. Explicit key file.
    if key_file is not None:
        path = Path(key_file)
        if warn:
            _warn_loose_permissions(path)
        return _parse_key(path.read_text(), source=str(path))

    # 2. Environment variable.
    if ENV_VAR in environ and environ[ENV_VAR].strip():
        return _parse_key(environ[ENV_VAR], source=f"${ENV_VAR}")

    # 3. Config file.
    if cfg.exists():
        if warn:
            _warn_loose_permissions(cfg)
        return _parse_key(cfg.read_text(), source=str(cfg))

    # 4. Auto-generate.
    if not autogenerate:
        raise FileNotFoundError(
            f"no watermark key found (looked at {ENV_VAR} and {cfg}); "
            "provide --key-file or set the env var"
        )
    key = generate_key()
    _persist_key(cfg, key)
    if warn:
        print(
            f"notice: generated a new watermark key at {cfg} (mode 0600). "
            "Back it up: without it you cannot extract existing marks.",
            file=sys.stderr,
        )
    return key


def derive_subkeys(master: bytes) -> Subkeys:
    """Derive independent PRNG and encryption subkeys from the master."""
    if len(master) != KEY_SIZE:
        raise ValueError(f"master key must be {KEY_SIZE} bytes, got {len(master)}")

    def _hkdf(info: bytes) -> bytes:
        return HKDF(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=None,
            info=info,
        ).derive(master)

    return Subkeys(prng=_hkdf(_INFO_PRNG), enc=_hkdf(_INFO_ENC))
