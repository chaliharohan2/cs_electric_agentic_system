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
import re
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from cs_agent.tool_errors import NEXT_STEP, failed, tool_error_message


def _signature(call: dict[str, Any]) -> str:
    """A call's identity: its name and arguments, order-insensitive."""
    return json.dumps(
        {"name": call.get("name"), "args": call.get("args") or {}},
        sort_keys=True,
        default=str,
    )


def _earlier_calls(messages: list[AnyMessage]) -> dict[str, int]:
    """Signature to 1-based call number, for every call already *answered well*.

    A failed call is deliberately not recorded. Short-circuiting one would tell
    the model its result "still stands" when the result was an error, and —
    worse — would launder a repeated failure into a successful-looking tool
    message, so `tool_failures` never rises and the failure limit never trips.
    One run spent 443 short-circuits on a single malformed tool call that way,
    stopping only when the operator interrupted it. Re-running a failed call
    costs at most the same error again, and the failure budget ends it.
    """
    outcome = _outcomes(messages)
    seen: dict[str, int] = {}
    index = 0
    for message in messages[:-1]:
        for call in getattr(message, "tool_calls", None) or []:
            index += 1
            if outcome.get(call.get("id")) is False:
                continue
            seen.setdefault(_signature(call), index)
    return seen


def _outcomes(messages: list[AnyMessage]) -> dict[str, bool]:
    """Whether each answered call succeeded, keyed on its tool_call_id."""
    return {
        message.tool_call_id: not failed(message)
        for message in messages
        if isinstance(message, ToolMessage)
    }


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


_IDENTIFIER = re.compile(r"[a-z0-9_]+")


def _did_you_mean(requested: str, known: list[str]) -> str | None:
    """The one bound tool a mangled name can only have been reaching for.

    Ollama's tool-call parser sometimes splits a name across two calls when the
    model emits Qwen's XML form instead of JSON: one turn produced
    `cat\n</parameter` and `alogue_map` for a single `catalogue_map`. The
    leading identifier run of the wreckage still prefixes exactly one real tool,
    and saying so turns several wasted turns into one. Only an unambiguous match
    is offered — a guess that names the wrong tool is worse than no guess.
    """
    match = _IDENTIFIER.search(requested.lower())
    if not match or len(match.group()) < 3:
        return None
    fragment = match.group()
    hits = [name for name in known if fragment in name]
    return hits[0] if len(hits) == 1 else None


def _invalid_name_message(call: dict[str, Any], known: list[str]) -> ToolMessage:
    """Reject an unknown tool name with something the model can act on.

    LangGraph's own message lists every tool and stops there, which on a
    malformed payload leaves the model to work out that its *syntax* was the
    problem rather than its choice of tool.
    """
    requested = call.get("name") or ""
    note = (
        f"'{requested}' is not a tool. Emit the call as JSON with the name "
        "exactly as published — a name broken across two calls means the "
        "payload was malformed, not that the tool is missing."
    )
    if suggestion := _did_you_mean(requested, known):
        note += f" You appear to have meant {suggestion}."
    return ToolMessage(
        content=json.dumps(
            {"error": note, "available_tools": known, "next_step": NEXT_STEP}
        ),
        tool_call_id=call["id"],
        name=requested or "unknown",
        status="error",
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

        # Names are checked here rather than left to ToolNode so a malformed
        # payload gets an error that names the likely tool and the likely cause.
        known = sorted(tool.name for tool in tools)
        bound = set(known)
        invalid = [
            _invalid_name_message(call, known)
            for call in calls
            if (call.get("name") or "") not in bound
        ]
        calls = [call for call in calls if (call.get("name") or "") in bound]
        if not calls:
            return {"messages": invalid}

        seen = _earlier_calls(messages)
        fresh = [call for call in calls if _signature(call) not in seen]
        repeats = [
            _repeat_message(call, seen[_signature(call)])
            for call in calls
            if _signature(call) in seen
        ]
        if not fresh:
            return {"messages": [*invalid, *repeats]}
        if not repeats and not invalid:
            return inner.invoke(state, config=config)

        # Hand ToolNode only the fresh calls; it answers exactly what it is
        # given, and every call still gets a result so the thread stays valid.
        trimmed = AIMessage(
            content=last.content, tool_calls=fresh, id=getattr(last, "id", None)
        )
        result = inner.invoke({**state, "messages": [*messages[:-1], trimmed]}, config=config)
        produced = result["messages"] if isinstance(result, dict) else result
        return {"messages": [*invalid, *produced, *repeats]}

    return run
