"""Human-in-the-loop clarification node."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from cs_agent.graph.state import AgentState


def _question(parameter: str) -> str:
    label = parameter.replace("_", " ").strip()
    return f"What {label} should be used?"


def clarify(state: AgentState) -> dict[str, Any]:
    plan = state.get("plan") or {}
    questions = [_question(item) for item in plan.get("open_params", [])[:3]]
    if not questions:
        questions = ["What additional operating requirement should be considered?"]
    answer = interrupt({"questions": questions})
    if isinstance(answer, dict):
        rendered = "; ".join(f"{key}: {value}" for key, value in answer.items())
    else:
        rendered = str(answer)
    return {
        "messages": [
            HumanMessage(
                content="Clarification answers supplied by the user: " + rendered
            )
        ],
        "clarify_count": state.get("clarify_count", 0) + 1,
    }
