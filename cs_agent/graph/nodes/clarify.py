"""Human-in-the-loop clarification node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from cs_agent.graph.nodes.planner import enrich_question_with_params
from cs_agent.graph.state import AgentState
from cs_agent.llm import get_model

PROMPT = (Path(__file__).parents[2] / "prompts" / "clarify.md").read_text(
    encoding="utf-8"
)


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _param_already_known(param: str, known: dict[str, Any]) -> bool:
    needle = param.lower().replace("_", " ")
    for key, value in known.items():
        blob = f"{key} {value}".lower().replace("_", " ")
        if needle in blob or str(key).lower().replace("_", " ") in needle:
            return True
    return False


def clarify(state: AgentState) -> dict[str, Any]:
    plan = state.get("plan") or {}
    session = state.get("session") or {}
    known = {
        **(plan.get("known_params") or {}),
        **(session.get("resolved_params") or {}),
    }
    open_params = [
        param
        for param in (plan.get("open_params") or [])
        if not _param_already_known(param, known)
    ]
    question = state.get("standalone_question") or ""
    if not open_params:
        return {
            "plan": {**plan, "needs_clarification": False},
            "clarify_count": state.get("clarify_count", 0) + 1,
            "standalone_question": enrich_question_with_params(question, known),
        }
    draft = get_model("clarify").invoke(
        [
            SystemMessage(content=PROMPT),
            HumanMessage(
                content=(
                    "Open parameters to clarify:\n"
                    + json.dumps(open_params)
                    + "\nKnown parameters:\n"
                    + json.dumps(known, default=str)
                    + "\nUser question:\n"
                    + question
                )
            ),
        ]
    )
    text = _content_text(draft.content).strip()
    questions = [
        line.split(".", 1)[1].strip() if "." in line else line.strip()
        for line in text.splitlines()
        if line.strip() and (line.strip()[0].isdigit() or line.strip().startswith("-"))
    ][:3]
    if not questions:
        questions = [
            f"What {param.replace('_', ' ')} should be used? (leave blank to skip)"
            for param in open_params[:3]
        ] or ["What additional operating requirement should be considered? (none)"]

    answer = interrupt({"questions": questions})
    if isinstance(answer, dict):
        rendered = "; ".join(f"{key}: {value}" for key, value in answer.items())
        resolved = answer
    else:
        rendered = str(answer)
        resolved = {"clarification": rendered}
    merged = {**known, **resolved}
    return {
        "messages": [
            HumanMessage(
                content="Clarification answers supplied by the user: " + rendered
            )
        ],
        "clarify_count": state.get("clarify_count", 0) + 1,
        "standalone_question": enrich_question_with_params(question, merged),
        "session": {
            **session,
            "resolved_params": merged,
        },
    }
