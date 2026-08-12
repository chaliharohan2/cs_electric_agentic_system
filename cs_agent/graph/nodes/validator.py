"""Deterministic final-answer validation and bounded repair."""

from __future__ import annotations

from typing import Any

from cs_agent.graph.state import AgentState
from cs_agent.validation.numeric_fidelity import (
    strip_unsupported_sentences,
    validate_numeric_fidelity,
)


def validator(state: AgentState) -> dict[str, Any]:
    draft = state.get("draft") or ""
    messages = state.get("messages", [])
    first_content = getattr(messages[0], "content", "") if messages else ""
    user_text = first_content if isinstance(first_content, str) else str(first_content)
    result = validate_numeric_fidelity(
        draft, state.get("evidence", []), user_text=user_text
    )
    previous = state.get("validation") or {}
    attempt = int(previous.get("attempt", 0)) + 1
    validation = {
        "passed": result.passed,
        "attempt": attempt,
        "errors": result.errors,
        "numbers_total": result.numbers_total,
        "matched": result.matched,
        "unmatched": result.unmatched,
        "action": "accepted" if result.passed else "retry_composer",
    }
    update: dict[str, Any] = {"validation": validation}
    if not result.passed and attempt >= 2:
        update["draft"] = strip_unsupported_sentences(
            draft, result.unsupported_sentences
        )
        validation["action"] = "stripped_unsupported_sentences"
    return update
