# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 millaguie <https://www.millaguie.net/>
"""Localized text for the visible "traceability-protected" notice.

Only the visible notice is translated; the machinery is language-agnostic.

Scope/limitation (honest): the visible notice is rendered with the built-in
Helvetica font (PDF) and DejaVu (images), which cover Latin-1 / Western-European
scripts. So this table holds the languages that render correctly out of the box.
Cyrillic, Greek, CJK, Arabic, etc. would need an embedded Unicode/CJK font and
are intentionally NOT included (they would render as missing glyphs). Templates
use a plain ASCII hyphen for the same reason.

Each entry is (standalone_warning, with_contact_template). Pass --lang es / fr /
es_ES (region is matched by language prefix). Translations are best-effort;
review wording for legal precision in your jurisdiction.
"""

from __future__ import annotations

DEFAULT = "en"

NOTICES: dict[str, tuple[str, str]] = {
    "en": (
        "Traceability-protected document",
        "Traceability-protected document - if found, contact: {contact}",
    ),
    "es": (
        "Documento protegido por trazabilidad",
        "Documento protegido por trazabilidad - si lo encuentras, contacta: {contact}",
    ),
    "fr": (
        "Document protégé par traçabilité",
        "Document protégé par traçabilité - si trouvé, contactez : {contact}",
    ),
    "de": (
        "Durch Rückverfolgbarkeit geschütztes Dokument",
        "Durch Rückverfolgbarkeit geschütztes Dokument - bei Fund bitte kontaktieren: {contact}",
    ),
    "it": (
        "Documento protetto da tracciabilità",
        "Documento protetto da tracciabilità - se trovato, contattare: {contact}",
    ),
    "pt": (
        "Documento protegido por rastreabilidade",
        "Documento protegido por rastreabilidade - se encontrado, contacte: {contact}",
    ),
    "nl": (
        "Document beschermd door traceerbaarheid",
        "Document beschermd door traceerbaarheid - indien gevonden, neem contact op: {contact}",
    ),
    "ca": (
        "Document protegit per traçabilitat",
        "Document protegit per traçabilitat - si el trobes, contacta: {contact}",
    ),
    "gl": (
        "Documento protexido por rastrexabilidade",
        "Documento protexido por rastrexabilidade - se o atopas, contacta: {contact}",
    ),
    "eu": (
        "Trazabilitateak babestutako dokumentua",
        "Trazabilitateak babestutako dokumentua - aurkituz gero, jarri harremanetan: {contact}",
    ),
    "da": (
        "Sporbarhedsbeskyttet dokument",
        "Sporbarhedsbeskyttet dokument - hvis fundet, kontakt: {contact}",
    ),
    "sv": (
        "Spårbarhetsskyddat dokument",
        "Spårbarhetsskyddat dokument - om funnen, kontakta: {contact}",
    ),
    "nb": (
        "Sporbarhetsbeskyttet dokument",
        "Sporbarhetsbeskyttet dokument - hvis funnet, kontakt: {contact}",
    ),
    "fi": (
        "Jäljitettävyyssuojattu asiakirja",
        "Jäljitettävyyssuojattu asiakirja - jos löydät, ota yhteyttä: {contact}",
    ),
    "id": (
        "Dokumen terlindungi keterlacakan",
        "Dokumen terlindungi keterlacakan - jika ditemukan, hubungi: {contact}",
    ),
}


def available() -> list[str]:
    """Sorted list of supported language codes."""
    return sorted(NOTICES)


def normalize(lang: str | None) -> str:
    """Resolve a locale code (e.g. 'es_ES', 'pt-BR') to a supported language."""
    if not lang:
        return DEFAULT
    code = lang.lower().replace("-", "_")
    if code in NOTICES:
        return code
    base = code.split("_")[0]
    return base if base in NOTICES else DEFAULT


def is_supported(lang: str | None) -> bool:
    """True if ``lang`` maps to a translation (not just the default fallback)."""
    if not lang:
        return True
    code = lang.lower().replace("-", "_")
    return code in NOTICES or code.split("_")[0] in NOTICES


def notice(lang: str | None, contact: str | None = None) -> str:
    """Localized notice text; with the contact appended when given."""
    warning, with_contact = NOTICES[normalize(lang)]
    return with_contact.format(contact=contact) if contact else warning
