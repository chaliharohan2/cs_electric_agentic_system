"""Evidence-constrained answer composition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from cs_agent.config.limits import get_limits
from cs_agent.contracts import SufficiencyResult
from cs_agent.graph.state import AgentState
from cs_agent.llm import get_model, structured

PROMPT = (Path(__file__).parents[2] / "prompts" / "composer.md").read_text(
    encoding="utf-8"
)


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _evidence_table(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "(none)"
    lines = []
    for item in evidence:
        lines.append(
            " | ".join(
                [
                    f"tool={item.get('tool')}",
                    f"sku={item.get('sku_code')}",
                    f"spec={item.get('spec_id')}",
                    f"value_num={item.get('value_num')}",
                    f"value_min={item.get('value_min')}",
                    f"value_max={item.get('value_max')}",
                    f"value_display={item.get('value_display')}",
                    f"value_kind={item.get('value_kind')}",
                    f"unit={item.get('unit')}",
                    f"source={item.get('source_of_truth')}",
                    f"text={json.dumps(item.get('text'), default=str)}",
                ]
            )
        )
    return "\n".join(lines)


def composer_sufficiency(state: AgentState) -> dict[str, Any]:
    limits = get_limits()
    used = state.get("tool_calls_made", 0) - state.get("turn_tool_calls_start", 0)
    remaining = limits.global_tool_budget - used
    if remaining <= 0:
        return {
            "sufficiency": {
                "sufficient": True,
                "gaps": [],
                "budget_exhausted": True,
            }
        }
    result = structured(
        "composer",
        [
            SystemMessage(
                content=(
                    "Check whether the specialist reports contain enough evidence to "
                    "answer the user's question. Identify only concrete, retrievable "
                    "gaps and name the specialist best able to fill each. Do not request "
                    "a blanket rerun."
                )
            ),
            HumanMessage(
                content=json.dumps(
                    {
                        "question": state.get("standalone_question"),
                        "reports": state.get("reports", {}),
                    },
                    default=str,
                )
            ),
        ],
        SufficiencyResult,
    )
    revision_allowed = (
        not result.sufficient
        and state.get("revision_round", 0) < limits.composer_revision_rounds
    )
    sufficiency = result.model_dump()
    sufficiency["revision_allowed"] = revision_allowed
    update: dict[str, Any] = {"sufficiency": sufficiency}
    if revision_allowed:
        update["revision_round"] = state.get("revision_round", 0) + 1
    return update


def compose_final(state: AgentState) -> dict[str, Any]:
    assumptions = state.get("assumptions") or []
    system = (
        PROMPT.replace(
            "{reports_json}",
            json.dumps(state.get("reports", {}), indent=2, default=str),
        )
        .replace(
            "{assumptions}",
            "\n".join(f"- {item}" for item in assumptions) if assumptions else "(none)",
        )
    )
    if state.get("sufficiency", {}).get("budget_exhausted"):
        system += "\nThe global tool budget was exhausted; disclose unresolved evidence gaps."
    response = get_model("composer").invoke(
        [
            SystemMessage(content=system),
            HumanMessage(
                content=(
                    f"Question: {state.get('standalone_question')}\n"
                    "Compose the final answer from the reports now."
                )
            ),
        ]
    )
    draft = _text(response.content).strip()
    if not draft:
        # Preserve an existing draft if the composer is invoked manually as a
        # retry and the model returns no content.
        return {"draft": state.get("draft")}
    session = state.get("session") or {}
    reports = state.get("reports", {})
    cited_skus: list[str] = []
    focus_family = session.get("focus_family")
    for report in reports.values():
        for source in report.get("sources", []):
            if source.get("sku_code"):
                cited_skus.append(source["sku_code"])
        cited_skus.extend(report.get("representative_skus", []))
        cited_skus.extend(
            item.get("sku_code")
            for item in report.get("candidates", [])
            if item.get("sku_code")
        )
        if not focus_family and report.get("families"):
            focus_family = report["families"][0].get("name")
    focus_skus = list(dict.fromkeys(cited_skus))
    turn = {
        "question": state.get("standalone_question"),
        "intent": (state.get("plan") or {}).get("intent"),
        "agents_used": list(reports),
        "answer_summary": draft[:500],
    }
    updated_session = {
        **session,
        "turns": [*session.get("turns", []), turn],
        "focus_skus": focus_skus or session.get("focus_skus", []),
        "focus_family": focus_family,
        "resolved_params": session.get("resolved_params", {}),
        "prior_reports": reports,
    }
    return {"draft": draft, "session": updated_session}


# Backward-compatible import name.
composer = compose_final
