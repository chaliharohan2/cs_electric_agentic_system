"""Tool failures returned to the caller instead of aborting the run.

A tool that raises used to kill the whole graph, discarding every fact already
retrieved. Returning the error as a tool result lets the model correct its own
arguments, which is usually all that is wrong. The budget stops that becoming an
endless retry loop.

This sits outside ``cs_agent.tools`` deliberately: the analytics subgraph needs it,
and that package's registry imports the subgraph, so importing it from there would
close an import cycle.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence

from langchain_core.messages import AnyMessage, ToolMessage

from cs_agent.config.limits import get_limits

# Failed tool calls allowed per run, across every tool, before the graph stops
# calling tools and answers with whatever it already has.
TOOL_FAILURE_LIMIT = get_limits().tool_failure_limit

NEXT_STEP = (
    "Fix the arguments and call the tool again, or call a different tool. "
    f"After {TOOL_FAILURE_LIMIT} failed tool calls no further tools run."
)

# Argument mistakes worth naming, because the database error alone does not say
# which argument to change.
_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"invalid input syntax for type "
            r"(?:double precision|numeric|integer|bigint)",
            re.IGNORECASE,
        ),
        "The gte, lte and eq filter operators compare against numeric columns, so "
        "their value must be a number. To match text use op='contains', and to "
        "match an ordering-code axis such as mounting or poles pass it in facets.",
    ),
    (
        re.compile(r"validation error|field required|input should be", re.IGNORECASE),
        "The arguments did not match the tool's schema. Re-read the argument names "
        "and types, and send only the fields the tool declares.",
    ),
)


def tool_error_message(exc: Exception) -> str:
    """Render ``exc`` as a tool result the model can act on."""
    detail = f"{type(exc).__name__}: {exc}".strip()
    payload = {"error": detail, "next_step": NEXT_STEP}
    for pattern, hint in _HINTS:
        if pattern.search(detail):
            payload["hint"] = hint
            break
    return json.dumps(payload)


def trailing_tool_messages(
    messages: Sequence[AnyMessage] | None,
) -> list[ToolMessage]:
    """The tool results produced by the most recent tool node run."""
    collected: list[ToolMessage] = []
    for message in reversed(messages or []):
        if not isinstance(message, ToolMessage):
            break
        collected.append(message)
    collected.reverse()
    return collected


def failed(message: ToolMessage) -> bool:
    """Whether ``message`` reports a call the model needs to redo.

    An exception raised by the tool arrives as ``status="error"``, but the
    backends report a rejected argument or a bad SELECT by returning an ``error``
    field instead of raising. Both are the same thing to the caller, and counting
    only the first would leave the budget unreachable for SQL, which never raises.
    """
    if message.status == "error":
        return True
    content = message.content
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            return False
    return isinstance(content, dict) and bool(content.get("error"))


def count_failures(messages: Iterable[ToolMessage]) -> int:
    """How many of ``messages`` report a failed tool call."""
    return sum(1 for message in messages if failed(message))
