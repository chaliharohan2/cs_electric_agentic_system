"""Planner node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from cs_agent.config.limits import get_limits
from cs_agent.contracts import Plan
from cs_agent.graph.state import AgentState
from cs_agent.llm import structured

PROMPT = (Path(__file__).parents[2] / "prompts" / "planner.md").read_text(
    encoding="utf-8"
)

USER_PARAMS_MARKER = "User-provided parameters:"


def enrich_question_with_params(question: str, params: dict[str, Any]) -> str:
    """Append clarification answers so later nodes see them on the question."""
    base = question.split(f"\n\n{USER_PARAMS_MARKER}", 1)[0].rstrip()
    if not params:
        return base
    rendered = "; ".join(f"{key}: {value}" for key, value in params.items())
    return f"{base}\n\n{USER_PARAMS_MARKER} {rendered}"


def known_params_from_state(state: AgentState) -> dict[str, Any]:
    session = state.get("session") or {}
    prior = (state.get("plan") or {}).get("known_params") or {}
    return {**prior, **(session.get("resolved_params") or {})}


def planner(state: AgentState) -> dict[str, Any]:
    limits = get_limits()
    question = state.get("standalone_question") or str(
        state.get("messages", [])[-1].content
    )
    known = known_params_from_state(state)
    clarify_count = state.get("clarify_count", 0)
    prior_open = list((state.get("plan") or {}).get("open_params") or [])
    plan_model = structured(
        "planner",
        [
            SystemMessage(
                content=PROMPT.replace("{max_stages}", str(limits.max_stages))
            ),
            HumanMessage(
                content=json.dumps(
                    {
                        "question": question,
                        "known_params": known,
                        "prior_open_params": prior_open,
                        "clarify_count": clarify_count,
                        "max_clarify_rounds": limits.clarify_rounds,
                    },
                    default=str,
                )
            ),
        ],
        Plan,
    )
    # Collapse anything past the stage cap onto the last stage rather than
    # dropping it: an over-long plan should run flatter, not lose an agent.
    # Allowance is left at zero — the runtime sizes it per stage at dispatch,
    # once it knows what the earlier stages actually spent.
    for brief in plan_model.dispatch:
        brief.stage = min(brief.stage, limits.max_stages)
        brief.parameters = {**known, **(brief.parameters or {})}
    plan = plan_model.model_dump()
    plan["known_params"] = {**known, **(plan.get("known_params") or {})}
    assumptions = list(state.get("assumptions", []))
    if known:
        provided = (
            "Proceeding with user-provided parameters: "
            + ", ".join(f"{key}={value}" for key, value in known.items())
        )
        if provided not in assumptions:
            assumptions.append(provided)
    if (
        clarify_count >= limits.clarify_rounds
        and plan["needs_clarification"]
    ):
        assumptions.extend(
            f"Proceeding without confirmed {parameter}"
            for parameter in plan["open_params"]
            if f"Proceeding without confirmed {parameter}" not in assumptions
            and str(parameter).lower().replace("_", " ")
            not in " ".join(f"{key} {value}" for key, value in known.items()).lower()
        )
        plan["needs_clarification"] = False
    return {
        "plan": plan,
        "dispatch": plan["dispatch"],
        "assumptions": assumptions,
        "standalone_question": enrich_question_with_params(question, known),
    }
