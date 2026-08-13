"""Planner node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_core.messages import HumanMessage

from cs_agent.config.limits import get_limits
from cs_agent.contracts import Plan
from cs_agent.graph.state import AgentState
from cs_agent.llm import structured

PROMPT = (Path(__file__).parents[2] / "prompts" / "planner.md").read_text(
    encoding="utf-8"
)


def planner(state: AgentState) -> dict[str, Any]:
    question = state.get("standalone_question") or str(
        state.get("messages", [])[-1].content
    )
    plan_model = structured(
        "planner",
        [SystemMessage(content=PROMPT), HumanMessage(content=question)],
        Plan,
    )
    limits = get_limits()
    used_this_turn = (
        state.get("tool_calls_made", 0) - state.get("turn_tool_calls_start", 0)
    )
    remaining = max(0, limits.global_tool_budget - used_this_turn)
    count = max(1, len(plan_model.dispatch))
    allowance = min(limits.per_agent_tool_budget, remaining // count)
    for brief in plan_model.dispatch:
        brief.allowance = allowance
    plan = plan_model.model_dump()
    assumptions = list(state.get("assumptions", []))
    if (
        state.get("clarify_count", 0) >= limits.clarify_rounds
        and plan["needs_clarification"]
    ):
        assumptions.extend(
            f"Proceeding without confirmed {parameter}"
            for parameter in plan["open_params"]
            if f"Proceeding without confirmed {parameter}" not in assumptions
        )
        plan["needs_clarification"] = False
    return {
        "plan": plan,
        "dispatch": plan["dispatch"],
        "assumptions": assumptions,
    }
