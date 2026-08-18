"""Provider-agnostic structured output with validate-then-retry."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from cs_agent.llm.factory import get_model

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


class StructuredOutputError(RuntimeError):
    def __init__(self, node: str, last_raw: str | None = None):
        self.node = node
        self.last_raw = last_raw
        super().__init__(f"Structured output failed for node '{node}' after retries")


def strip_fences(text: str) -> str:
    text = text.strip()
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text


def schema_instruction(schema: type[BaseModel]) -> str:
    """The wording that asks for a schema-shaped JSON object.

    Public because a caller continuing an existing conversation has to place it
    itself: `structured` puts it first, which is right for a one-shot call and
    wrong when the messages before it are a transcript the server has already
    cached. Passing it as the last message keeps that prefix byte-identical.
    """
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    return (
        "Respond with ONLY a JSON object matching this JSON Schema. "
        "No markdown fences, no commentary.\n\n"
        f"{schema_json}"
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


def structured(
    node: str,
    messages: list[BaseMessage],
    schema: type[T],
    attempts: int = 2,
    tools: list[object] | None = None,
) -> T:
    """Ask for a schema-shaped JSON object, validating and retrying.

    ``tools`` are bound but never expected to be called. It exists for a caller
    continuing a tool-using conversation: a server renders the tool schema into
    the prompt prefix, so asking the same messages *without* tools is a
    different prefix and re-reads the whole transcript from cold — measured at
    808 tok/s against 91,611 tok/s for the identical text with tools bound.
    """
    model = get_model(node)
    if tools:
        model = model.bind_tools(tools)
    msgs: list[BaseMessage] = list(messages)
    has_schema_hint = any(
        isinstance(m, (SystemMessage, HumanMessage))
        and "JSON Schema" in (m.content if isinstance(m.content, str) else "")
        for m in msgs
    )
    if not has_schema_hint:
        msgs = [SystemMessage(content=schema_instruction(schema))] + msgs

    last_raw: str | None = None
    for _ in range(attempts + 1):
        raw = _content_text(model.invoke(msgs).content)
        last_raw = raw
        try:
            return schema.model_validate_json(strip_fences(raw))
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            msgs = msgs + [
                AIMessage(content=raw),
                HumanMessage(content=f"Invalid output. Fix these errors:\n{e}"),
            ]
    raise StructuredOutputError(node, last_raw=last_raw)
