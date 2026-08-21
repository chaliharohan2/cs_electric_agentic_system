"""Expand a specialist's citations into the report the pipeline reads.

The model writes what only it can write — the summary, why an entry fits, the
gaps and caveats, the findings that are judgement rather than retrieval — and
names everything else. This module turns those names back into facts, reading
the tool payloads the specialist already received.

Why it is worth the indirection: on a captured `spec_selection` report, all 95
leaf values under `key_specs` were verbatim in a payload the specialist had in
hand, and 89% of them were *already* restated in the same report's own findings
or summary. The model was writing each value a third time, at 34 tok/s, with no
check that what it wrote matched what the catalogue publishes. Measured
field-by-field, asking for citations instead takes that report from 8,990
characters of generation to 4,879.

The two properties that matter more than the tokens:

* a value in the report is a value a tool returned, because nothing else can
  reach the report at all; and
* a `(sku_code, spec_id)` the specialist never retrieved is an error here,
  where before it was a valid report and a wrong answer.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AnyMessage

from cs_agent.backends.payload_shape import merge_scope

# Carried onto an expanded fact. `spec_id` is what was cited; the rest is what
# the catalogue publishes against it. `source_of_truth` rides along because it
# varies per spec where a document reference does not — a price fact reads
# `pricelist_table` beside a `brochure` fact on the same SKU — and a price
# citation is built from it.
FACT_FIELDS = ("value_display", "unit", "source_of_truth")


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The SKU rows of a search result, flat or grouped, scope merged back."""
    rows = [row for row in payload.get("hits") or [] if isinstance(row, dict)]
    for group in payload.get("groups") or []:
        if isinstance(group, dict):
            rows.extend(
                row for row in group.get("sample_hits") or [] if isinstance(row, dict)
            )
    return [merge_scope(payload, row) for row in rows]


def fact_index(items: list[tuple[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Every retrieved fact, keyed by the SKU and spec it belongs to.

    First writer wins, so a fact from `get_sku` — which returns the whole row —
    is not overwritten by a thinner copy attached to a later search hit.

    A `(sku, spec_id)` is not quite unique in the catalogue: 317 pairs across
    325 of 11,238 SKUs publish more than one distinct value, `terminal_block_count`
    arriving as both "4 Nos." and "12 Nos." on the same code. Those collapse to
    the first here. Distinguishing them needs `sku_fact.row_id` on the payload
    rows, which is deliberately not carried yet — it is an internal id, and 2.9%
    of SKUs do not justify putting one in front of the model on every call.
    """
    index: dict[tuple[str, str], dict[str, Any]] = {}

    def add(sku: Any, fact: Any) -> None:
        if not isinstance(fact, dict) or not isinstance(sku, str) or not sku:
            return
        spec = fact.get("spec_id")
        if not isinstance(spec, str) or not spec:
            return
        index.setdefault((sku, spec), fact)

    for _tool, payload in items:
        if not isinstance(payload, dict):
            continue
        sku = payload.get("sku_code")
        for key in ("facts", "specs"):
            for fact in payload.get(key) or []:
                add(
                    (fact.get("sku_code") if isinstance(fact, dict) else None) or sku,
                    fact,
                )
        for row in _rows(payload):
            for fact in row.get("specs") or []:
                add(row.get("sku_code") or sku, fact)
        for row in payload.get("rows") or []:
            if isinstance(row, dict):
                for fact in row.get("facts") or []:
                    add(
                        (fact.get("sku_code") if isinstance(fact, dict) else None)
                        or row.get("sku_code"),
                        fact,
                    )
    return index


def _from_evidence(evidence: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """The same index built from normalized evidence, as a second source.

    A payload shape this module does not know about still reaches
    `record_evidence._extract`, so a citation that misses the payload index can
    still be honoured rather than dropped.
    """
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in evidence or []:
        sku, spec = row.get("sku_code"), row.get("spec_id")
        if isinstance(sku, str) and sku and isinstance(spec, str) and spec:
            index.setdefault((sku, spec), row)
    return index


def _fact(
    index: dict[tuple[str, str], dict[str, Any]], sku: Any, spec: Any
) -> dict[str, Any] | None:
    if not isinstance(sku, str) or not isinstance(spec, str):
        return None
    return index.get((sku, spec))


def expand_key_specs(
    candidate: dict[str, Any], index: dict[tuple[str, str], dict[str, Any]]
) -> list[str]:
    """Fill a candidate's cited specs from the index; return what was not found.

    The candidate's own `sku_code` addresses every one of them: the reference
    under a key_spec repeated it on 466 of 469 measured rows, and the three that
    differed hung under an entry that named no SKU of its own.
    """
    sku = candidate.get("sku_code")
    missing: list[str] = []
    filled: list[dict[str, Any]] = []
    for spec in candidate.get("key_specs") or []:
        spec_id = spec.get("spec_id") if isinstance(spec, dict) else spec
        if not spec_id:
            continue
        fact = _fact(index, sku, spec_id)
        if fact is None:
            missing.append(f"{sku or candidate.get('family')}/{spec_id}")
            continue
        entry = {"spec_id": spec_id}
        for field in FACT_FIELDS:
            if fact.get(field) is not None:
                entry[field] = fact[field]
        if "value_display" not in entry and fact.get("value_num") is not None:
            entry["value_display"] = str(fact["value_num"])
        filled.append(entry)
    candidate["key_specs"] = filled
    return missing


# Units a `value_display` already conveys, so restating them reads as a mistake.
# `count` is dimensionless and the label beside it names what is being counted,
# which turned "Number of poles: 4" into "Number of poles 4 count" (6,688 rows
# carry it). `INR` is spelled ₹ in every price display. Every other unit in the
# catalogue's top twenty — A, V, mm, Hz, kA, ms, operations, kg — reads
# correctly after the number and is left alone.
IMPLIED_UNITS = {"count", "inr"}


def displayed(fact: dict[str, Any]) -> str | None:
    """A fact's value with its unit, without saying the unit twice.

    `value_display` is already unit-bearing most of the time — "400 A", "IP54",
    "₹60,910" — so appending `unit` unconditionally produced "400 A A".
    """
    value = fact.get("value_display")
    if value is None and fact.get("value_num") is not None:
        value = fact["value_num"]
    if value is None:
        return None
    text = str(value).strip()
    unit = (fact.get("unit") or "").strip()
    if (
        unit
        and unit.lower() not in IMPLIED_UNITS
        and not text.lower().endswith(unit.lower())
    ):
        text = f"{text} {unit}"
    return text


def statement_for(sku: str, fact: dict[str, Any]) -> str:
    """One retrieved fact as a sentence, inventing nothing."""
    label = fact.get("spec_label") or fact.get("spec_id")
    return f"{sku} {label}: {displayed(fact)}"


def expand_findings(
    findings: list[dict[str, Any]], index: dict[tuple[str, str], dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Turn cited findings into stated ones, leaving prose findings alone.

    A finding that cites nothing is judgement and passes through untouched. One
    that cites is a value list, and the values come from here rather than from
    the model — which is the point: on the captured report those were six of
    eight findings and every value in them had already been written twice.

    Several cited specs on one SKU become one finding, not several, because
    that is how the model wrote them by hand and how the composer reads them.
    """
    out: list[dict[str, Any]] = []
    missing: list[str] = []
    for finding in findings or []:
        cited = [spec for spec in finding.get("cite") or [] if spec]
        if not cited:
            finding.pop("cite", None)
            out.append(finding)
            continue
        sku = (finding.get("source") or {}).get("sku_code")
        parts: list[str] = []
        for spec_id in cited:
            fact = _fact(index, sku, spec_id)
            if fact is None:
                missing.append(f"{sku}/{spec_id}")
                continue
            value = displayed(fact)
            if value is None:
                missing.append(f"{sku}/{spec_id}")
                continue
            parts.append(f"{fact.get('spec_label') or spec_id} {value}")
        if not parts:
            # Nothing behind it. Dropping the finding is right: keeping the
            # citation would hand the composer a claim with no value in it, and
            # inventing a statement is the thing this module exists to prevent.
            continue
        finding.pop("cite", None)
        if not finding.get("statement"):
            finding["statement"] = f"{sku}: " + ", ".join(parts) + "."
        out.append(finding)
    return out, missing


def expand_standards(
    standards: list[dict[str, Any]], index: dict[tuple[str, str], dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fill each standards claim's value from the fact it names."""
    out: list[dict[str, Any]] = []
    missing: list[str] = []
    for claim in standards or []:
        sku, spec_id = claim.get("sku_code"), claim.get("spec_id")
        fact = _fact(index, sku, spec_id)
        if fact is None:
            missing.append(f"{sku}/{spec_id}")
            continue
        value = displayed(fact)
        if value is None:
            missing.append(f"{sku}/{spec_id}")
            continue
        claim["value_display"] = value
        if fact.get("source_of_truth"):
            claim["source_of_truth"] = fact["source_of_truth"]
        out.append(claim)
    return out, missing


def format_report(
    report: dict[str, Any],
    messages: list[AnyMessage],
    evidence: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Expand every citation in a report. Returns the report and what was missed.

    The misses are returned rather than raised: a specialist that cited one
    spec it never retrieved should still deliver the rest of its report, and the
    gate is where an empty result becomes a failure. They are recorded as gaps
    so the composer can see the shape of what is absent.
    """
    from cs_agent.subgraphs.agents.report_modes import payloads

    index = {**_from_evidence(evidence), **fact_index(payloads(messages))}
    missing: list[str] = []

    for candidate in report.get("candidates") or []:
        if isinstance(candidate, dict):
            missing.extend(expand_key_specs(candidate, index))
    if report.get("findings"):
        report["findings"], missed = expand_findings(report["findings"], index)
        missing.extend(missed)
    if report.get("standards"):
        report["standards"], missed = expand_standards(report["standards"], index)
        missing.extend(missed)
    return report, missing
