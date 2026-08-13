"""Rewrite follow-up turns into self-contained catalogue questions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from cs_agent.contracts import IntakeResult
from cs_agent.graph.state import AgentState
from cs_agent.llm import structured

PROMPT = (Path(__file__).parents[2] / "prompts" / "intake.md").read_text(
    encoding="utf-8"
)


def intake(state: AgentState) -> dict[str, Any]:
    messages = state.get("messages", [])
    question = str(messages[-1].content) if messages else ""
    session = state.get("session") or {}
    if not session.get("turns"):
        return {
            "standalone_question": question,
            "referenced_skus": [],
            "is_followup": False,
            "turn_tool_calls_start": state.get("tool_calls_made", 0),
        }
    result = structured(
        "intake",
        [
            SystemMessage(
                content=PROMPT.replace(
                    "{session_json}", json.dumps(session, default=str)
                )
            ),
            HumanMessage(content=question),
        ],
        IntakeResult,
    )
    updated_session = {**session}
    updated_session["resolved_params"] = {
        **session.get("resolved_params", {}),
        **result.carried_params,
    }
    return {
        "standalone_question": result.standalone_question,
        "referenced_skus": result.referenced_skus,
        "is_followup": result.is_followup,
        "session": updated_session,
        "turn_tool_calls_start": state.get("tool_calls_made", 0),
    }
