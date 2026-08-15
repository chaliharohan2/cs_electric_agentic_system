"""Catalogue text matching used by the fixture backend.

Catalogue labels carry typographic punctuation and spacing that nobody retypes
exactly — ``ACB – WiNmaster 2`` uses an en dash, ``CSPTD Series SPD’s`` a curly
apostrophe. Every term here is matched two ways: each whitespace-separated part
must appear in a punctuation-folded copy of the value, or the whole term must
appear once punctuation and spacing are stripped entirely.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

PUNCTUATION_EQUIVALENTS = {
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2212": "-",  # minus sign
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
}

_TRANSLATION = str.maketrans(PUNCTUATION_EQUIVALENTS)
_WHITESPACE = re.compile(r"\s+")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def normalize(value: Any) -> str:
    """Lowercase, fold punctuation variants, and collapse whitespace."""
    return _WHITESPACE.sub(" ", str(value or "").translate(_TRANSLATION).lower()).strip()


def squash(value: Any) -> str:
    """Reduce to alphanumerics so spacing and hyphenation stop mattering."""
    return _NON_ALPHANUMERIC.sub("", str(value or "").lower())


def terms_of(term: Any) -> list[str]:
    """Split a search term into the parts that must all be present."""
    return [part for part in normalize(term).split(" ") if squash(part)]


def matches(value: Any, wanted: Any) -> bool:
    """Whether ``value`` satisfies the search term ``wanted``."""
    if wanted is None or str(wanted).strip() == "":
        return True
    parts = terms_of(wanted)
    haystack = normalize(value)
    if parts and all(part in haystack for part in parts):
        return True
    collapsed = squash(wanted)
    return bool(collapsed) and collapsed in squash(value)


def matches_any(values: Sequence[Any], wanted: Any) -> bool:
    """Whether any of ``values`` satisfies the search term ``wanted``."""
    return any(matches(value, wanted) for value in values)
