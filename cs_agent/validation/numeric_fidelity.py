"""Deterministic numeric-claim validation against recorded evidence."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from cs_agent.graph.state import Evidence

REL_TOL = 1e-6
_STANDARD = re.compile(r"\b(?:IEC|EN|IS)\s*\d+(?:-\d+)*\b", re.IGNORECASE)
_CODE = re.compile(
    r"(?<!\w)(?=[A-Z0-9()./-]*[A-Z])(?=[A-Z0-9()./-]*\d)"
    r"[A-Z0-9][A-Z0-9()./-]{3,}",
    re.IGNORECASE,
)
_NUMBER = re.compile(
    r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*(kA|A|kW|W|V|kV|Hz|kHz)?\b",
    re.IGNORECASE,
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[!?])\s+|(?<!\d)\.(?!\d)\s*|\n+")
_UNITS = {
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


def _normalise(value: float, unit: str | None) -> tuple[float, str | None]:
    if not unit:
        return value, None
    canonical, multiplier = _UNITS.get(unit.lower(), (unit, 1.0))
    return value * multiplier, canonical


def _supported(
    sentence: str,
    value: float,
    unit: str | None,
    evidence: Iterable[Evidence],
) -> bool:
    claim_value, claim_unit = _normalise(value, unit)
    for item in evidence:
        candidates: list[tuple[float, str | None]] = []
        if item.get("value_num") is not None:
            candidates.append((item["value_num"], item.get("unit")))
        display = item.get("value_display")
        if item.get("value_kind") in {"text", "set"} and display:
            candidates.extend(
                (float(match.group(1)), match.group(2))
                for match in _NUMBER.finditer(display)
            )
        for expected, expected_unit in candidates:
            evidence_value, evidence_unit = _normalise(expected, expected_unit)
            if claim_unit != evidence_unit:
                continue
            if not math.isclose(
                claim_value, evidence_value, rel_tol=REL_TOL, abs_tol=0
            ):
                continue
            return True
        lower = item.get("value_min")
        upper = item.get("value_max")
        if lower is not None and upper is not None:
            normal_lower, lower_unit = _normalise(lower, item.get("unit"))
            normal_upper, upper_unit = _normalise(upper, item.get("unit"))
            if (
                claim_unit == lower_unit == upper_unit
                and normal_lower <= claim_value <= normal_upper
            ):
                return True
    return False


def validate_numeric_fidelity(
    draft: str, evidence: list[Evidence], user_text: str = ""
) -> FidelityResult:
    sku_codes = [item["sku_code"] for item in evidence if item.get("sku_code")]
    user_numbers = {
        (float(match.group(1)), (match.group(2) or "").lower())
        for match in _NUMBER.finditer(user_text)
    }
    errors: list[str] = []
    unsupported: list[str] = []
    unmatched: list[str] = []
    numbers_total = 0
    matched = 0
    for original in _sentences(draft):
        cleaned = _STANDARD.sub("", original)
        cleaned = _CODE.sub("", cleaned)
        for sku_code in sku_codes:
            cleaned = re.sub(
                re.escape(sku_code or ""), "", cleaned, flags=re.IGNORECASE
            )
        bad_claims = []
        number_matches = list(_NUMBER.finditer(cleaned))
        for index, number in enumerate(number_matches):
            value = float(number.group(1))
            unit = number.group(2)
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
