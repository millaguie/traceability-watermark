# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Tests for notice localization."""
from __future__ import annotations

from wmlib import i18n


def test_default_is_english():
    assert i18n.notice(None) == i18n.NOTICES["en"][0]
    assert "Traceability" in i18n.notice("en")


def test_spanish_and_region_variant():
    assert i18n.notice("es").startswith("Documento protegido")
    # Region variants resolve by language prefix.
    assert i18n.notice("es_ES") == i18n.notice("es")
    assert i18n.notice("ES-es") == i18n.notice("es")


def test_contact_is_appended_localized():
    out = i18n.notice("es", "me@example.com")
    assert "me@example.com" in out
    assert "contacta" in out


def test_unknown_language_falls_back_to_english():
    assert i18n.notice("xx") == i18n.notice("en")
    assert i18n.is_supported("xx") is False
    assert i18n.is_supported("es_ES") is True


def test_all_templates_are_latin1_renderable():
    # The visible notice font is Latin-1; every shipped string must encode.
    for warning, template in i18n.NOTICES.values():
        warning.encode("latin-1")
        template.format(contact="x@y.z").encode("latin-1")
