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


def composer(state: AgentState) -> dict[str, Any]:
    assumptions = state.get("assumptions") or []
    system = (
        PROMPT.replace("{evidence_table}", _evidence_table(state.get("evidence", [])))
        .replace(
            "{assumptions}",
            "\n".join(f"- {item}" for item in assumptions) if assumptions else "(none)",
        )
    )
    failures = state.get("tool_failures", 0)
    if failures:
        # Absent evidence and unretrieved evidence are different claims, and only
        # this node can tell the reader which one it is looking at.
        system += (
            f"\n\n{failures} catalogue lookup(s) failed during this run, so the "
            "evidence above may be incomplete. Where the evidence does not cover "
            "part of the question, say the data could not be retrieved. Do not "
            "state or imply that C&S does not publish it."
        )
    response = get_model("composer").invoke(
        [
            SystemMessage(content=system),
            *state.get("messages", [])[:1],
            HumanMessage(
                content="Compose the final answer now using only the evidence above."
            ),
        ]
    )
    draft = _text(response.content).strip()
    if not draft:
        # Preserve an existing draft if the composer is invoked manually as a
        # retry and the model returns no content.
        return {"draft": state.get("draft")}
    return {"draft": draft}
