"""Deterministic numeric-claim validation against recorded evidence."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from cs_agent.graph.state import Evidence

REL_TOL = 1e-6
_STANDARD = re.compile(r"\b(?:IEC|EN|IS)\s*\d+(?:-\d+)*\b", re.IGNORECASE)
_CODE = re.compile(r"\b(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)+\b", re.IGNORECASE)
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


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_BOUNDARY.split(text) if part.strip()]


def _normalise(value: float, unit: str | None) -> tuple[float, str | None]:
    if not unit:
        return value, None
    canonical, multiplier = _UNITS.get(unit.lower(), (unit, 1.0))
    return value * multiplier, canonical


def _contains_number(sentence: str, expected: float) -> bool:
    return any(
        math.isclose(float(match.group(1)), expected, rel_tol=REL_TOL, abs_tol=0)
        for match in _NUMBER.finditer(sentence)
    )


def _conditions_present(sentence: str, evidence: Evidence) -> bool:
    return all(
        _contains_number(sentence, float(value))
        if isinstance(value, (int, float))
        else str(value).lower() in sentence.lower()
        for value in evidence["conditions"].values()
    )


def _supported(
    sentence: str,
    value: float,
    unit: str | None,
    evidence: Iterable[Evidence],
) -> bool:
    claim_value, claim_unit = _normalise(value, unit)
    for item in evidence:
        candidates: list[tuple[float, str | None]] = []
        if item["value_num"] is not None:
            candidates.append((item["value_num"], item["unit"]))
        if item["page"] is not None:
            candidates.append((float(item["page"]), None))
        for condition_value in item["conditions"].values():
            if isinstance(condition_value, (int, float)):
                candidates.append((float(condition_value), unit))
        for expected, expected_unit in candidates:
            evidence_value, evidence_unit = _normalise(expected, expected_unit)
            if claim_unit != evidence_unit:
                continue
            if not math.isclose(
                claim_value, evidence_value, rel_tol=REL_TOL, abs_tol=0
            ):
                continue
            if item["value_num"] == expected and not _conditions_present(sentence, item):
                continue
            return True
    return False


def validate_numeric_fidelity(
    draft: str, evidence: list[Evidence]
) -> FidelityResult:
    family_ids = [item["family_id"] for item in evidence if item["family_id"]]
    errors: list[str] = []
    unsupported: list[str] = []
    for original in _sentences(draft):
        cleaned = _STANDARD.sub("", original)
        cleaned = _CODE.sub("", cleaned)
        for family_id in family_ids:
            cleaned = re.sub(
                rf"\b{re.escape(family_id or '')}\b", "", cleaned, flags=re.IGNORECASE
            )
        bad_claims = []
        for number in _NUMBER.finditer(cleaned):
            value = float(number.group(1))
            unit = number.group(2)
            if not _supported(original, value, unit, evidence):
                bad_claims.append(number.group(0).strip())
        if bad_claims:
            errors.append(
                f"Unsupported numeric claim(s) {bad_claims} in: {original}"
            )
            unsupported.append(original)
    return FidelityResult(not errors, errors, unsupported)


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
