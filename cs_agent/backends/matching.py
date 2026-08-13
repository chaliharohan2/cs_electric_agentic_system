"""Catalogue text matching shared by the Postgres and fixture backends.

Catalogue labels carry typographic punctuation and spacing that nobody retypes
exactly — ``ACB – WiNmaster 2`` uses an en dash, ``CSPTD Series SPD’s`` a curly
apostrophe. A single ``ILIKE '%term%'`` therefore misses ``ACB - WiNmaster 2``,
``ACB WiNmaster 2`` and ``WiNmaster2`` alike. Every term here is matched two
ways: each whitespace-separated part must appear in a punctuation-folded copy of
the value, or the whole term must appear once punctuation and spacing are
stripped entirely.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

# Typographic characters mapped to the ASCII equivalent a caller is likely to
# type. Keys and values must stay the same length for SQL ``translate``.
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


def like_escape(value: str) -> str:
    """Escape LIKE wildcards in an already-normalized term."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


_TRANSLATE_ARGS = (
    f"{_sql_text(''.join(PUNCTUATION_EQUIVALENTS))}, "
    f"{_sql_text(''.join(PUNCTUATION_EQUIVALENTS.values()))}"
)


def normalized_sql(expression: str) -> str:
    """SQL mirroring :func:`normalize` for a column expression."""
    return (
        f"regexp_replace(lower(translate({expression}, {_TRANSLATE_ARGS})), "
        "'\\s+', ' ', 'g')"
    )


def squashed_sql(expression: str) -> str:
    """SQL mirroring :func:`squash` for a column expression."""
    return f"regexp_replace(lower({expression}), '[^a-z0-9]+', '', 'g')"


def text_predicate(
    expressions: Sequence[str], term: Any
) -> tuple[str, list[Any]]:
    """Return ``(sql, params)`` matching ``term`` against any of ``expressions``.

    Mirrors :func:`matches`, so both backends accept the same spellings.
    """
    parts = terms_of(term)
    collapsed = squash(term)
    per_expression: list[str] = []
    params: list[Any] = []
    for expression in expressions:
        alternatives: list[str] = []
        if parts:
            normalized = normalized_sql(expression)
            alternatives.append(
                " AND ".join(f"{normalized} LIKE %s" for _ in parts)
            )
            params.extend(f"%{like_escape(part)}%" for part in parts)
        if collapsed:
            alternatives.append(f"{squashed_sql(expression)} LIKE %s")
            params.append(f"%{like_escape(collapsed)}%")
        if alternatives:
            per_expression.append(
                "(" + ") OR (".join(alternatives) + ")"
            )
    if not per_expression:
        return "TRUE", []
    return "(" + " OR ".join(per_expression) + ")", params


def distinctive_words(term: Any) -> list[str]:
    """Words worth suggesting on, dropping fragments like ``2`` that match anything."""
    words = re.findall(r"[A-Za-z0-9]+", str(term or ""))
    return [word for word in words if len(word) > 2] or words


def any_term_predicate(
    expressions: Sequence[str], wanted: Sequence[Any]
) -> tuple[str, list[Any]]:
    """Return ``(sql, params)`` matching any term in ``wanted``."""
    clauses: list[str] = []
    params: list[Any] = []
    for term in wanted:
        clause, clause_params = text_predicate(expressions, term)
        if clause == "TRUE":
            return "TRUE", []
        clauses.append(clause)
        params.extend(clause_params)
    if not clauses:
        return "TRUE", []
    return "(" + " OR ".join(clauses) + ")", params
