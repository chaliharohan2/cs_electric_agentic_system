"""Planner node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from cs_agent.graph.state import AgentState
from cs_agent.llm import structured

PROMPT = (Path(__file__).parents[2] / "prompts" / "planner.md").read_text(
    encoding="utf-8"
)


class Plan(BaseModel):
    intent: str
    categories: list[str] = Field(default_factory=list)
    target_facts: list[str] = Field(default_factory=list)
    known_params: dict[str, Any] = Field(default_factory=dict)
    open_params: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    strategy: str


def planner(state: AgentState) -> dict[str, Any]:
    plan = structured(
        "planner",
        [SystemMessage(content=PROMPT), *state.get("messages", [])],
        Plan,
    ).model_dump()
    assumptions = list(state.get("assumptions", []))
    if state.get("clarify_count", 0) >= 2 and plan["needs_clarification"]:
        assumptions.extend(
            f"Proceeding without confirmed {parameter}"
            for parameter in plan["open_params"]
            if f"Proceeding without confirmed {parameter}" not in assumptions
        )
        plan["needs_clarification"] = False
    return {"plan": plan, "assumptions": assumptions}
