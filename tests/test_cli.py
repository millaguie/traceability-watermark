# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Tests for the subcommand CLI (embed / extract / verify + visible)."""

from __future__ import annotations

import numpy as np
from PIL import Image

from wmlib import cli

from .conftest import make_textured_image

ID = "banco-x-2026-05"


def _write_image(path) -> str:
    Image.fromarray(make_textured_image()).save(path)
    return str(path)


def _key_file(tmp_path) -> str:
    p = tmp_path / "k.key"
    p.write_text("ab" * 32)
    return str(p)


def test_embed_then_extract_roundtrip(tmp_path):
    src = _write_image(tmp_path / "in.png")
    out = str(tmp_path / "out.png")
    key = _key_file(tmp_path)

    assert cli.main(["embed", src, "--id", ID, "-o", out, "--key-file", key]) == 0
    # extract prints the id and returns 0
    assert cli.main(["extract", out, "--key-file", key]) == 0


def test_verify_match_and_mismatch(tmp_path):
    src = _write_image(tmp_path / "in.png")
    out = str(tmp_path / "out.png")
    key = _key_file(tmp_path)
    cli.main(["embed", src, "--id", ID, "-o", out, "--key-file", key])

    assert cli.main(["verify", out, "--id", ID, "--key-file", key]) == 0
    assert cli.main(["verify", out, "--id", "someone-else", "--key-file", key]) == 1


def test_extract_on_unmarked_image_returns_1(tmp_path):
    src = _write_image(tmp_path / "plain.png")
    key = _key_file(tmp_path)
    assert cli.main(["extract", src, "--key-file", key]) == 1


def test_embed_requires_id_or_visible(tmp_path, capsys):
    src = _write_image(tmp_path / "in.png")
    key = _key_file(tmp_path)
    rc = cli.main(["embed", src, "-o", str(tmp_path / "o.png"), "--key-file", key])
    assert rc == 1
    assert "requires --id" in capsys.readouterr().err


def test_visible_mode_warns_and_stamps(tmp_path, capsys):
    src = _write_image(tmp_path / "in.png")
    out = str(tmp_path / "stamp.png")
    rc = cli.main(
        ["embed", src, "--visible", "--text", "Shared with Ana", "-o", out, "--no-date"]
    )
    assert rc == 0
    assert "DETERRENT ONLY" in capsys.readouterr().err
    # The visible stamp visibly changes the image.
    assert not np.array_equal(np.asarray(Image.open(src)), np.asarray(Image.open(out)))


def test_extract_missing_file_returns_1(tmp_path):
    key = _key_file(tmp_path)
    assert cli.main(["extract", str(tmp_path / "nope.png"), "--key-file", key]) == 1


def test_embed_with_contact_then_read_without_key(tmp_path, capsys):
    src = _write_image(tmp_path / "in.png")
    out = str(tmp_path / "out.png")
    key = _key_file(tmp_path)
    rc = cli.main(
        [
            "embed",
            src,
            "--id",
            ID,
            "--contact",
            "found@x.io",
            "-o",
            out,
            "--key-file",
            key,
        ]
    )
    assert rc == 0
    capsys.readouterr()
    # The `contact` subcommand needs no --key-file.
    assert cli.main(["contact", out]) == 0
    assert "found@x.io" in capsys.readouterr().out


def test_contact_subcommand_none_returns_1(tmp_path):
    src = _write_image(tmp_path / "plain.png")
    assert cli.main(["contact", src]) == 1


def test_notice_lang_flag_stamps_localized(tmp_path):
    src = _write_image(tmp_path / "in.png")
    out = str(tmp_path / "out.png")
    key = _key_file(tmp_path)
    rc = cli.main(
        [
            "embed",
            src,
            "--id",
            ID,
            "--notice",
            "--lang",
            "es_ES",
            "-o",
            out,
            "--key-file",
            key,
        ]
    )
    assert rc == 0
    # The notice landed (footer band darkens the bottom rows).
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(out))
    assert a[-10:].mean() < a[:10].mean()


def test_unknown_lang_warns_but_succeeds(tmp_path, capsys):
    src = _write_image(tmp_path / "in.png")
    key = _key_file(tmp_path)
    rc = cli.main(
        [
            "embed",
            src,
            "--id",
            ID,
            "--notice",
            "--lang",
            "zz",
            "-o",
            str(tmp_path / "o.png"),
            "--key-file",
            key,
        ]
    )
    assert rc == 0
    assert "not available" in capsys.readouterr().err
