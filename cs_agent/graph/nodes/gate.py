"""Deterministic structural checks for specialist reports."""

from __future__ import annotations

from typing import Any

from cs_agent.contracts import (
    GateFailure,
    GateResult,
    REPORT_SCHEMAS,
    brief_depth,
)
from cs_agent.graph.state import AgentState


def _violations(agent: str, raw: dict[str, Any], depth: str = "detailed") -> list[str]:
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
        for candidate in report.candidates:
            # A shortlist entry has to be orderable or at least locatable. Which
            # of the two depends on the brief, not on this check: "find me the
            # 16A 2P 6kA code" wants the code, "which ranges offer 4-pole" wants
            # the range, and only the entry that names neither is unusable.
            if not (candidate.sku_code or candidate.family):
                failures.append("Every candidate needs a sku_code or a family.")
    elif agent == "discovery":
        if not report.families:
            failures.append("Return at least one family.")
        if depth == "overview":
            # An overview answers at range level, so ordering codes are not the
            # deliverable — the question that narrows the next turn is. Demanding
            # SKUs here is what drove the retrieval this depth exists to avoid.
            if not report.follow_up_questions:
                failures.append(
                    "An overview must return at least one follow_up_question."
                )
        elif not report.representative_skus and not any(
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
    # An overview never reaches a SKU, so a sku_code is not something it could
    # supply: what it quotes is a category-level span off the taxonomy page, not
    # a claim about one product. Enforcing the SKU rule here made the check
    # unsatisfiable by construction and cost a full re-run of the specialist.
    #
    # A family is the other honest answer to "sourced against what". Some
    # specification claims are true of a range rather than a product — which
    # spec IDs it publishes, over how many SKUs, between which observed bounds,
    # how many of its members a filter matched — and no member code sources
    # them. Demanding one made this check unsatisfiable for those too: on the
    # 4-pole ACB run the only finding it failed was "the 'poles' spec is
    # composite-valued in ACB – AH-AHA (3 composite SKUs excluded)", a statement
    # about the family's registry with no SKU behind it, and the retry bought
    # the pass by pinning a representative code onto range-level counts.
    if depth != "overview":
        for finding in report.findings:
            if finding.kind == "specification" and not (
                finding.source and (finding.source.sku_code or finding.source.family)
            ):
                failures.append(
                    "Every specification finding needs a SourceRef naming the "
                    "sku_code it was retrieved against, or the family when the "
                    "claim is about the range rather than one product."
                )
    # An unexpanded citation means the formatter did not run, or ran against a
    # fact index that never held the spec. Either way what reached here is a
    # claim with no value in it, which reads to the composer as a specification
    # the catalogue does not publish. The model cannot fix this by rewriting —
    # the values were never its to supply — so it is stated as the fault it is.
    unexpanded = [
        f"{candidate.sku_code or candidate.family}/{spec.spec_id}"
        for candidate in getattr(report, "candidates", [])
        for spec in candidate.key_specs
        if spec.value_display is None
    ]
    unexpanded += [
        f"{claim.sku_code}/{claim.spec_id}"
        for claim in getattr(report, "standards", [])
        if not claim.value_display
    ]
    if any(not finding.statement for finding in report.findings):
        unexpanded.append("a finding carrying a citation but no statement")
    if unexpanded:
        failures.append(
            "Citations reached the report without being expanded into values: "
            + ", ".join(sorted(set(unexpanded))[:6])
        )
    # One sentence per distinct problem: the list is replayed to the specialist
    # as its revision note, and four copies of a rule read as four faults.
    return list(dict.fromkeys(failures))


def gate(state: AgentState) -> dict[str, Any]:
    """Check the stage that just finished, not the whole plan.

    Later stages have not run yet, so gating every brief would fail them all
    and burn the retry budget on work that was never dispatched.
    """
    stage = int(state.get("stage_index", 1) or 1)
    failures = []
    for brief in state.get("dispatch", []):
        if int(brief.get("stage", 1) or 1) != stage:
            continue
        agent = brief["agent"]
        report = state.get("reports", {}).get(agent)
        violations = (
            ["The specialist did not return a report."]
            if report is None
            else _violations(agent, report, brief_depth(brief))
        )
        if violations:
            failures.append(GateFailure(agent=agent, violations=violations))
    result = GateResult(ok=not failures, failures=failures)
    update: dict[str, Any] = {"gate_result": result.model_dump()}
    if failures:
        retries = dict(state.get("gate_retries") or {})
        retries[str(stage)] = retries.get(str(stage), 0) + 1
        update["gate_retries"] = retries
    else:
        # Transcripts are held only so a failing stage can resume on its own
        # work. Once the stage passes, nothing will read them again, and each
        # one is tens of thousands of tokens that would otherwise be copied
        # into every later checkpoint.
        update["transcripts"] = {"__reset__": []}
    return update
