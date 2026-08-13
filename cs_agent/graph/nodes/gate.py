"""Deterministic structural checks for specialist reports."""

from __future__ import annotations

from typing import Any

from cs_agent.contracts import GateFailure, GateResult, REPORT_SCHEMAS
from cs_agent.graph.state import AgentState


def _violations(agent: str, raw: dict[str, Any]) -> list[str]:
    schema = REPORT_SCHEMAS[agent]
    try:
        report = schema.model_validate(raw)
    except Exception as exc:
        return [f"Report does not match {schema.__name__}: {exc}"]
    failures: list[str] = []
    if agent == "spec_selection":
        if not report.candidates and not (
            report.no_candidates_reason and report.filters_tried
        ):
            failures.append(
                "Return a candidate or a no_candidates_reason with filters_tried."
            )
    elif agent == "discovery":
        if not report.families:
            failures.append("Return at least one family.")
        if not report.representative_skus and not any(
            "representative" in gap.lower() or "sku" in gap.lower()
            for gap in report.gaps
        ):
            failures.append("Return a representative SKU or an explicit gap.")
    elif agent == "comparison":
        if report.status == "no_result":
            if not report.gaps:
                failures.append("A no_result comparison needs a reason.")
        elif not report.table.axes or len(report.table.rows) < 2:
            failures.append("Return non-empty axes and at least two SKU rows.")
    elif agent == "compliance":
        if not report.standards and not report.not_established:
            failures.append("Return a standards claim or not_established entry.")
    elif agent == "solution_advisory":
        if not report.catalog_backed and not report.engineering_guidance:
            failures.append("Return catalogue-backed or engineering guidance.")
        for slot in report.recommended_slots:
            if not (
                slot.sku_code
                or slot.family
                or "no c&s product" in slot.resolution.lower()
            ):
                failures.append(
                    f"Resolve advisory slot {slot.function!r} or mark no C&S product."
                )
    for finding in report.findings:
        if finding.kind == "specification" and not (
            finding.source and finding.source.sku_code
        ):
            failures.append(
                "Every specification finding needs a SourceRef with sku_code."
            )
    return failures


def gate(state: AgentState) -> dict[str, Any]:
    failures = []
    for brief in state.get("dispatch", []):
        agent = brief["agent"]
        report = state.get("reports", {}).get(agent)
        violations = (
            ["The specialist did not return a report."]
            if report is None
            else _violations(agent, report)
        )
        if violations:
            failures.append(GateFailure(agent=agent, violations=violations))
    result = GateResult(ok=not failures, failures=failures)
    update: dict[str, Any] = {"gate_result": result.model_dump()}
    if failures:
        update["gate_retries"] = state.get("gate_retries", 0) + 1
    return update
