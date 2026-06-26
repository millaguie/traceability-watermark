# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Tests for key sourcing and subkey derivation.

Requirements encoded here:
  - Master key is sourced in order: explicit file -> env var -> config file.
  - If none exists, one is auto-generated and persisted with 0600 perms.
  - Subkeys (PRNG, encryption) are derived deterministically via HKDF and
    are distinct from each other and the master.
  - The secret never lives in code; everything comes from file/env/config.
"""

from __future__ import annotations

import stat

import pytest

from wmlib import keys


def test_generate_key_is_32_random_bytes():
    a = keys.generate_key()
    b = keys.generate_key()
    assert len(a) == 32 and len(b) == 32
    assert a != b  # astronomically unlikely to collide


def test_autogenerates_and_persists_with_0600(tmp_path):
    cfg = tmp_path / "key"
    assert not cfg.exists()
    master = keys.load_master_key(config_path=cfg, env={}, warn=False)
    assert len(master) == 32
    assert cfg.exists()
    mode = stat.S_IMODE(cfg.stat().st_mode)
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"
    # Second load returns the same persisted key (no regeneration).
    again = keys.load_master_key(config_path=cfg, env={}, warn=False)
    assert again == master


def test_explicit_key_file_takes_precedence(tmp_path):
    explicit = tmp_path / "explicit.key"
    explicit.write_text(("11" * 32) + "\n")
    cfg = tmp_path / "cfg.key"
    env = {"WATERMARK_KEY": "22" * 32}
    master = keys.load_master_key(
        key_file=str(explicit), config_path=cfg, env=env, warn=False
    )
    assert master == bytes.fromhex("11" * 32)


def test_env_var_used_when_no_explicit_file(tmp_path):
    cfg = tmp_path / "cfg.key"
    env = {"WATERMARK_KEY": "ab" * 32}
    master = keys.load_master_key(config_path=cfg, env=env, warn=False)
    assert master == bytes.fromhex("ab" * 32)
    assert not cfg.exists()  # env wins, nothing persisted


def test_rejects_wrong_length_key(tmp_path):
    bad = tmp_path / "bad.key"
    bad.write_text("00" * 16)  # only 16 bytes
    with pytest.raises(ValueError):
        keys.load_master_key(key_file=str(bad), env={}, warn=False)


def test_subkeys_are_deterministic_and_distinct():
    master = bytes.fromhex("ab" * 32)
    s1 = keys.derive_subkeys(master)
    s2 = keys.derive_subkeys(master)
    assert s1.prng == s2.prng
    assert s1.enc == s2.enc
    assert s1.prng != s1.enc != master
    assert len(s1.prng) == 32 and len(s1.enc) == 32


def test_different_masters_give_different_subkeys():
    s1 = keys.derive_subkeys(bytes.fromhex("ab" * 32))
    s2 = keys.derive_subkeys(bytes.fromhex("cd" * 32))
    assert s1.prng != s2.prng
    assert s1.enc != s2.enc
