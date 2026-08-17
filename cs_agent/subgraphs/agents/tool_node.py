"""A ToolNode that answers a repeated call from the transcript.

Specialists re-issue calls they have already made. In one measured run the
agent called `list_canonical_specs(family="Switch Sockets")`, got nothing back,
and called it three more times unchanged before trying a different approach —
four of its twenty tool calls spent on one dead end, each one re-sending the
same empty payload into a transcript the model then re-reads every turn.

Answering the repeat with a pointer costs a few tokens instead of a few
thousand, and says the one thing a second identical call cannot discover for
itself: the arguments have to change.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from cs_agent.tool_errors import tool_error_message


def _signature(call: dict[str, Any]) -> str:
    """A call's identity: its name and arguments, order-insensitive."""
    return json.dumps(
        {"name": call.get("name"), "args": call.get("args") or {}},
        sort_keys=True,
        default=str,
    )


def _earlier_calls(messages: list[AnyMessage]) -> dict[str, int]:
    """Signature to 1-based call number, for every call already answered."""
    seen: dict[str, int] = {}
    index = 0
    for message in messages[:-1]:
        for call in getattr(message, "tool_calls", None) or []:
            index += 1
            seen.setdefault(_signature(call), index)
    return seen


def _repeat_message(call: dict[str, Any], number: int) -> ToolMessage:
    return ToolMessage(
        content=json.dumps(
            {
                "repeat_of_call": number,
                "note": (
                    f"You already called {call.get('name')} with these exact "
                    f"arguments as call {number}. Its result is above and still "
                    "stands — re-reading it will not change it. Change the "
                    "arguments, call a different tool, or work with what you have."
                ),
            }
        ),
        tool_call_id=call["id"],
        name=call.get("name", "unknown"),
    )


def make_tool_node(tools: list[Any]):
    """Wrap ToolNode so identical repeat calls never reach a backend."""
    inner = ToolNode(tools, handle_tool_errors=tool_error_message)

    def run(state: dict[str, Any], config=None) -> dict[str, list[AnyMessage]]:
        messages = list(state.get("messages") or [])
        last = messages[-1] if messages else None
        calls = list(getattr(last, "tool_calls", None) or [])
        if not calls:
            return inner.invoke(state, config=config)

        seen = _earlier_calls(messages)
        fresh = [call for call in calls if _signature(call) not in seen]
        repeats = [
            _repeat_message(call, seen[_signature(call)])
            for call in calls
            if _signature(call) in seen
        ]
        if not fresh:
            return {"messages": repeats}
        if not repeats:
            return inner.invoke(state, config=config)

        # Hand ToolNode only the fresh calls; it answers exactly what it is
        # given, and every call still gets a result so the thread stays valid.
        trimmed = AIMessage(
            content=last.content, tool_calls=fresh, id=getattr(last, "id", None)
        )
        result = inner.invoke({**state, "messages": [*messages[:-1], trimmed]}, config=config)
        produced = result["messages"] if isinstance(result, dict) else result
        return {"messages": [*produced, *repeats]}

    return run
