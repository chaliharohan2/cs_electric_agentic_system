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
    context = (
        f"\nPlan:\n{json.dumps(state.get('plan'), default=str)}"
        f"\nAssumptions:\n{json.dumps(state.get('assumptions', []))}"
        f"\nRecorded evidence count: {len(state.get('evidence', []))}"
        f"\nTool calls remaining: {max(0, 12 - state.get('tool_calls_made', 0))}"
    )
    response = get_model("agent").bind_tools(TOOLS).invoke(
        [SystemMessage(content=PROMPT + context), *state.get("messages", [])]
    )
    calls = len(getattr(response, "tool_calls", []) or [])
    return {
        "messages": [response],
        "tool_calls_made": state.get("tool_calls_made", 0) + calls,
    }
