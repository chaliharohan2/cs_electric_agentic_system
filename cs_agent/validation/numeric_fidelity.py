"""Deterministic numeric-claim validation against recorded evidence."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from cs_agent.graph.state import Evidence

REL_TOL = 1e-6
# "IS" and "EN" are only standards when written as such: lower-cased they are the
# English words, and "the rated current is 630 A" must keep its figure.
_STANDARD = re.compile(r"\b(?:(?i:IEC)|IS|EN)\s*\d+(?:-\d+)*\b")
_CODE = re.compile(
    r"(?<!\w)(?=[A-Z0-9()./-]*[A-Z])(?=[A-Z0-9()./-]*\d)"
    r"[A-Z0-9][A-Z0-9()./-]{3,}",
    re.IGNORECASE,
)
# Digit groups may be separated, in Western or Indian style: 875,990 or 8,75,990.
_NUMBER = re.compile(
    r"(?<![\w.])(-?\d+(?:,\d{2,3})*(?:\.\d+)?)\s*(kA|A|kW|W|V|kV|Hz|kHz)?\b",
    re.IGNORECASE,
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[!?])\s+|(?<!\d)\.(?!\d)\s*|\n+")
# "### 5. ACB Type" and "3) Poles" number a section, they do not measure anything.
_ENUMERATOR = re.compile(r"^\s*(?:#{1,6}\s*)?\d+[.):]?\s*$")
_DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2212"
_QUOTES = "'\u2018\u2019"
# Prices are written with a leading marker ("₹5,79,370"), not a trailing unit,
# so the currency has to be read from the text before the digits.
_CURRENCY_BEFORE = re.compile(r"(?:₹|\bRs\.?|\bINR)\s*$", re.IGNORECASE)
_UNITS = {
    "inr": ("INR", 1.0),
    "a": ("A", 1.0),
    "ka": ("A", 1000.0),
    "w": ("W", 1.0),
    "kw": ("W", 1000.0),
    "v": ("V", 1.0),
    "kv": ("V", 1000.0),
    "hz": ("Hz", 1.0),
    "khz": ("Hz", 1000.0),
}


@dataclass(frozen=True)
class FidelityResult:
    passed: bool
    errors: list[str]
    unsupported_sentences: list[str]
    numbers_total: int
    matched: int
    unmatched: list[str]


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_BOUNDARY.split(text) if part.strip()]


def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


def _identifier_pattern(identifier: str) -> str:
    """Match a catalogue name however its punctuation and spacing were retyped."""
    parts = []
    for char in identifier:
        if char in _DASHES:
            parts.append(f"[{re.escape(_DASHES)}]")
        elif char in _QUOTES:
            parts.append(f"[{re.escape(_QUOTES)}]")
        elif char.isspace():
            parts.append(r"\s+")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


def _without_identifiers(sentence: str, identifiers: list[str]) -> str:
    """Remove ordering codes and catalogue names.

    "WiNmaster 2" and frame code "3P" name a product; the digits in them are not
    claims about a rating, so they must not be validated as such.
    """
    for identifier in sorted(identifiers, key=len, reverse=True):
        sentence = re.sub(
            _identifier_pattern(identifier), " ", sentence, flags=re.IGNORECASE
        )
    return sentence


def _normalise(value: float, unit: str | None) -> tuple[float, str | None]:
    if not unit:
        return value, None
    canonical, multiplier = _UNITS.get(unit.lower(), (unit, 1.0))
    return value * multiplier, canonical


def _comparable(
    value: float, unit: str | None, expected: float, expected_unit: str | None
) -> tuple[float, float]:
    """Put a claim and an evidence figure on one scale.

    Only one side usually names the unit. A decoded axis records the rating as a
    bare 630 and a canonical spec records the price as 875990 INR, while the
    answer writes "630 A" and "₹8,75,990". Where a unit is missing the figures
    are compared as written; where both name one they are converted first, so
    "80 kA" still fails against 80 V.
    """
    if unit and expected_unit:
        return _normalise(value, unit)[0], _normalise(expected, expected_unit)[0]
    return value, expected


def _supported(
    sentence: str,
    value: float,
    unit: str | None,
    evidence: Iterable[Evidence],
) -> bool:
    _, claim_unit = _normalise(value, unit)
    for item in evidence:
        candidates: list[tuple[float, str | None]] = []
        if item.get("value_num") is not None:
            candidates.append((item["value_num"], item.get("unit")))
        display = item.get("value_display")
        if item.get("value_kind") in {"text", "set"} and display:
            candidates.extend(
                (_to_float(match.group(1)), match.group(2))
                for match in _NUMBER.finditer(display)
            )
        for expected, expected_unit in candidates:
            _, evidence_unit = _normalise(expected, expected_unit)
            if claim_unit and evidence_unit and claim_unit != evidence_unit:
                continue
            claim_value, evidence_value = _comparable(
                value, unit, expected, expected_unit
            )
            if math.isclose(claim_value, evidence_value, rel_tol=REL_TOL, abs_tol=0):
                return True
        lower = item.get("value_min")
        upper = item.get("value_max")
        if lower is None or upper is None:
            continue
        bounds_unit = _normalise(lower, item.get("unit"))[1]
        if claim_unit and bounds_unit and claim_unit != bounds_unit:
            continue
        claim_value, low = _comparable(value, unit, lower, item.get("unit"))
        _, high = _comparable(value, unit, upper, item.get("unit"))
        if low <= claim_value <= high:
            return True
    return False


def validate_numeric_fidelity(
    draft: str, evidence: list[Evidence], user_text: str = ""
) -> FidelityResult:
    identifiers = [item["sku_code"] for item in evidence if item.get("sku_code")]
    identifiers += [
        item["value_display"]
        for item in evidence
        if item.get("value_kind") == "name" and item.get("value_display")
    ]
    user_numbers = {
        (_to_float(match.group(1)), (match.group(2) or "").lower())
        for match in _NUMBER.finditer(user_text)
    }
    errors: list[str] = []
    unsupported: list[str] = []
    unmatched: list[str] = []
    numbers_total = 0
    matched = 0
    for original in _sentences(draft):
        cleaned = _STANDARD.sub(" ", original)
        cleaned = _CODE.sub(" ", cleaned)
        cleaned = _without_identifiers(cleaned, identifiers)
        bad_claims = []
        number_matches = list(_NUMBER.finditer(cleaned))
        for index, number in enumerate(number_matches):
            value = _to_float(number.group(1))
            unit = number.group(2)
            if unit is None and _CURRENCY_BEFORE.search(cleaned[: number.start()]):
                unit = "INR"
            if unit is None and index + 1 < len(number_matches):
                next_number = number_matches[index + 1]
                separator = cleaned[number.end() : next_number.start()]
                if re.fullmatch(r"\s*(?:-|–|—|to)\s*", separator, re.IGNORECASE):
                    unit = next_number.group(2)
            token = number.group(0).strip()
            if (value, (unit or "").lower()) in user_numbers:
                continue
            if not unit and (
                1900 <= value <= 2100
                or bool(re.search(rf"\b{re.escape(token)}(?:st|nd|rd|th)\b", cleaned))
                or _ENUMERATOR.match(cleaned[: number.end()])
            ):
                continue
            numbers_total += 1
            if not _supported(original, value, unit, evidence):
                bad_claims.append(token)
                unmatched.append(token)
            else:
                matched += 1
        if bad_claims:
            errors.append(
                f"Unsupported numeric claim(s) {bad_claims} in: {original}"
            )
            unsupported.append(original)
    return FidelityResult(
        not errors, errors, unsupported, numbers_total, matched, unmatched
    )


def strip_unsupported_sentences(
    draft: str, unsupported_sentences: list[str]
) -> str:
    unsupported = {sentence.strip() for sentence in unsupported_sentences}
    kept = [sentence for sentence in _sentences(draft) if sentence not in unsupported]
    answer = ". ".join(kept).strip()
    if answer and draft.strip().endswith("."):
        answer += "."
    caveat = (
        "Some figures could not be verified against the catalogue and were removed."
    )
    return f"{answer}\n\n{caveat}".strip()
