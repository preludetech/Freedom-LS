"""Composition helpers for rendering two-character initials (e.g. avatar monograms)."""

from __future__ import annotations

import unicodedata


def is_latin(ch: str) -> bool:
    """Return True if the base form of ``ch`` is a basic-Latin / Latin-Extended letter.

    Used to decide whether initials can show two characters (``MJ``) or
    should fall back to a single grapheme (CJK, Arabic, etc.).
    """
    if not ch:
        return False
    decomposed = unicodedata.normalize("NFD", ch)
    base = decomposed[0]
    if not base.isalpha():
        return False
    name = unicodedata.name(base, "")
    return name.startswith("LATIN ")


def two_or_one(first: str, second: str) -> str:
    """Compose initials from up to two characters.

    Returns ``first.upper() + second.upper()`` if both are Latin letters;
    otherwise just ``first.upper()`` (a single grapheme works better for
    non-Latin scripts where two characters can read as a word fragment).
    """
    first_up = first.upper()
    if second and is_latin(first) and is_latin(second):
        return first_up + second.upper()
    return first_up
