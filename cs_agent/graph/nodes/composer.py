"""Evidence-constrained answer composition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from cs_agent.graph.state import AgentState
from cs_agent.llm import get_model

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


def composer(state: AgentState) -> dict[str, Any]:
    validation = state.get("validation") or {}
    correction = ""
    if validation.get("errors"):
        correction = (
            "\nCorrect every prior validation error:\n"
            + "\n".join(f"- {error}" for error in validation["errors"])
        )
    payload = {
        "plan": state.get("plan"),
        "assumptions": state.get("assumptions", []),
        "evidence": state.get("evidence", []),
    }
    response = get_model("composer").invoke(
        [
            SystemMessage(content=PROMPT + correction),
            *state.get("messages", [])[:1],
            HumanMessage(
                content="Compose the final answer from this data:\n"
                + json.dumps(payload, ensure_ascii=False, default=str)
            ),
        ]
    )
    return {"draft": _text(response.content).strip()}
