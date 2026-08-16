"""Compact an upstream specialist report for the stage that consumes it.

A later stage needs to know what an earlier one established, not how it got
there. Passing the whole report forward would push a stage's full findings,
sources and transcript-derived detail into every downstream prompt, which is
the duplication the staged pipeline exists to remove. Each digest keeps the
identifiers a downstream agent can act on — families, ordering codes, axes,
slots — plus the summary and the gaps that say what is still open.
"""

from __future__ import annotations

from typing import Any

# Enough for a downstream agent to work from, short enough that three of them
# stay well inside the prompt budget of a 27B model.
MAX_ITEMS = 8


def digest_report(report: dict[str, Any]) -> dict[str, Any]:
    """Reduce one specialist report to what a later stage can build on."""
    out: dict[str, Any] = {
        "status": report.get("status"),
        "summary": report.get("summary"),
    }
    if families := report.get("families"):
        out["families"] = [
            {
                "name": family.get("name"),
                "path": family.get("path"),
                "sku_count": family.get("sku_count"),
            }
            for family in families[:MAX_ITEMS]
            if isinstance(family, dict)
        ]
    if skus := report.get("representative_skus"):
        out["representative_skus"] = [str(sku) for sku in skus[:MAX_ITEMS]]
    if candidates := report.get("candidates"):
        out["candidates"] = [
            {
                "sku_code": candidate.get("sku_code"),
                "why_it_fits": candidate.get("why_it_fits"),
            }
            for candidate in candidates[:MAX_ITEMS]
            if isinstance(candidate, dict)
        ]
    if slots := report.get("recommended_slots"):
        out["recommended_slots"] = [
            {
                "function": slot.get("function"),
                "family": slot.get("family"),
                "sku_code": slot.get("sku_code"),
                "resolution": slot.get("resolution"),
            }
            for slot in slots[:MAX_ITEMS]
            if isinstance(slot, dict)
        ]
    table = report.get("table")
    if isinstance(table, dict) and table.get("rows"):
        out["compared_skus"] = list(table["rows"])[:MAX_ITEMS]
    if standards := report.get("standards"):
        out["standards"] = [
            {
                "sku_code": claim.get("sku_code"),
                "spec_id": claim.get("spec_id"),
                "value_display": claim.get("value_display"),
            }
            for claim in standards[:MAX_ITEMS]
            if isinstance(claim, dict)
        ]
    if reason := report.get("no_candidates_reason"):
        out["no_candidates_reason"] = reason
    if gaps := report.get("gaps"):
        out["gaps"] = [str(gap) for gap in gaps[:MAX_ITEMS]]
    return out


def upstream_digest(
    reports: dict[str, dict[str, Any]],
    dispatch: list[dict[str, Any]],
    before_stage: int,
    *,
    exclude: tuple[str, ...] = (),
) -> dict[str, dict[str, Any]]:
    """Digest every report produced by a stage earlier than ``before_stage``."""
    earlier = {
        brief["agent"]
        for brief in dispatch
        if int(brief.get("stage", 1)) < before_stage
        and brief.get("agent") not in exclude
    }
    return {
        agent: digest_report(report)
        for agent, report in (reports or {}).items()
        if agent in earlier
    }
