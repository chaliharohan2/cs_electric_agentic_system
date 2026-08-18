"""Reply to a turn the catalogue pipeline should not run for.

The planner decides scope, so reaching this node costs nothing beyond the one
short generation the reply itself needs: no specialist, no tool call, no gate,
no sufficiency pass. A job application used to walk the taxonomy looking for a
product called "R&D".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from cs_agent.config.contact import get_contact
from cs_agent.graph.state import AgentState
from cs_agent.llm import stream_answer

PROMPT = (Path(__file__).parents[2] / "prompts" / "out_of_scope.md").read_text(
    encoding="utf-8"
)

# What the user sees if the model returns nothing at all. Deliberately the
# "company" wording: a turn that reaches here is one the pipeline will not
# answer either way, so the reply has to stand on its own.
FALLBACK = (
    "That is not something I can take from here. Please go through "
    "{website} or call {phone}, and they will point you to the right team. "
    "If you have a question about the C&S range itself, I can help with that."
)


def out_of_scope(state: AgentState) -> dict[str, Any]:
    plan = state.get("plan") or {}
    scope = plan.get("scope") or "unrelated"
    contact = get_contact()
    system = (
        PROMPT.replace("{website}", contact.website)
        .replace("{phone}", contact.phone)
    )
    draft, streamed = stream_answer(
        "out_of_scope",
        [
            SystemMessage(content=system),
            HumanMessage(
                content=(
                    f"The user asked: {state.get('standalone_question') or ''}\n"
                    f"What they are actually after: "
                    f"{plan.get('scope_note') or '(not stated)'}\n"
                    f"scope: {scope}\n"
                    "Write the reply now."
                )
            ),
        ],
    )
    draft = draft.strip() or FALLBACK.format(
        website=contact.website, phone=contact.phone
    )
    session = state.get("session") or {}
    # Recorded like any other turn so intake can resolve a follow-up against it
    # — "what about a sales role?" needs to know what the last turn was about.
    turn = {
        "question": state.get("standalone_question"),
        "intent": plan.get("intent"),
        "agents_used": [],
        "out_of_scope": scope,
        "answer_summary": draft[:500],
    }
    return {
        "draft": draft,
        "draft_streamed": streamed,
        "session": {**session, "turns": [*session.get("turns", []), turn]},
    }
