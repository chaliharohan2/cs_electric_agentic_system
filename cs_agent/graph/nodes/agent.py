"""Tool-using evidence agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import SystemMessage

from cs_agent.graph.state import AgentState
from cs_agent.llm import get_model
from cs_agent.tools import TOOLS

PROMPT = (Path(__file__).parents[2] / "prompts" / "agent.md").read_text(
    encoding="utf-8"
)


def agent(state: AgentState) -> dict[str, Any]:
    plan_json = json.dumps(state.get("plan"), default=str)
    system = PROMPT.replace("{plan_json}", plan_json)
    if state.get("assumptions"):
        system += "\nAssumptions:\n" + json.dumps(state["assumptions"])
    remaining = max(0, 12 - state.get("tool_calls_made", 0))
    system += f"\nTool calls remaining: {remaining}"
    response = (
        get_model("agent")
        .bind_tools(TOOLS)
        .invoke([SystemMessage(content=system), *state.get("messages", [])])
    )
    calls = len(getattr(response, "tool_calls", []) or [])
    return {
        "messages": [response],
        "tool_calls_made": state.get("tool_calls_made", 0) + calls,
    }
