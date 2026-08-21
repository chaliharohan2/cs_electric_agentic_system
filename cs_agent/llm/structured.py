"""Provider-agnostic structured output with validate-then-retry."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping
from typing import TypeVar

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from cs_agent.llm.factory import get_model
from cs_agent.llm.streaming import generate
from cs_agent.observability import active_trace

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


def _prune(
    document: dict,
    hide: Mapping[str, Iterable[str]],
    limits: Mapping[str, int],
    scalars: Mapping[str, str] | None = None,
) -> dict:
    """Drop fields from a JSON Schema and cap list lengths, in place.

    ``hide`` is keyed on a definition name — or ``""`` for the top-level object —
    and names properties the model should never be shown. Hiding differs from
    removing: the pydantic model still accepts the field, so anything already
    holding a value keeps validating and code is free to fill it in afterwards.
    Only the *asking* changes.

    ``scalars`` goes further, replacing a whole definition with a plain string:
    ``{"KeySpec": "spec_id"}`` asks for ``["rated_current_a", "poles"]`` where
    the model would otherwise write an object apiece. Every ``$ref`` to that
    definition resolves to the string, so nothing else in the document has to
    change, and the pydantic model accepts the short form through a `before`
    validator. Worth the extra machinery only where the object is repeated:
    hiding three of four fields still leaves the model writing
    ``{"spec_id": "poles"}`` — 30 characters against 7 — once per row.
    """
    sections = {"": document, **(document.get("$defs") or {})}
    for name, fields in hide.items():
        properties = (sections.get(name) or {}).get("properties")
        if not properties:
            continue
        for field in fields:
            properties.pop(field, None)
        required = (sections.get(name) or {}).get("required")
        if required:
            sections[name]["required"] = [f for f in required if f not in fields]
    for field, cap in limits.items():
        if entry := (document.get("properties") or {}).get(field):
            entry["maxItems"] = cap
    for name, field in (scalars or {}).items():
        section = (document.get("$defs") or {}).get(name)
        if not section:
            continue
        described = ((section.get("properties") or {}).get(field) or {}).get(
            "description"
        )
        section.clear()
        section["type"] = "string"
        section["description"] = described or f"The {field}, as a bare string."
    return document


def asked_schema(
    schema: type[BaseModel],
    *,
    hide: Mapping[str, Iterable[str]] | None = None,
    limits: Mapping[str, int] | None = None,
    scalars: Mapping[str, str] | None = None,
) -> dict:
    """The JSON Schema document the model is actually shown.

    Split out from `schema_instruction` because the same document is what
    `structured` hands Ollama as `format`, so the grammar the decode is
    constrained to and the schema the prompt describes cannot drift apart.
    """
    document = schema.model_json_schema()
    if hide or limits or scalars:
        document = _prune(document, hide or {}, limits or {}, scalars)
    return document


def schema_instruction(
    schema: type[BaseModel],
    *,
    hide: Mapping[str, Iterable[str]] | None = None,
    limits: Mapping[str, int] | None = None,
    scalars: Mapping[str, str] | None = None,
) -> str:
    """The wording that asks for a schema-shaped JSON object.

    Public because a caller continuing an existing conversation has to place it
    itself: `structured` puts it first, which is right for a one-shot call and
    wrong when the messages before it are a transcript the server has already
    cached. Passing it as the last message keeps that prefix byte-identical.

    ``hide`` and ``limits`` shape what the model is asked for without changing
    what the schema accepts. This is the enforceable version of asking for a
    shorter report: a field the model is never shown cannot be written, whereas
    a paragraph requesting brevity was measured cutting output 23% on one
    question and *raising* it 22% on the next. ``limits`` is the softer of the
    two — `maxItems` is a strong hint rather than a guarantee, so a caller that
    depends on the cap has to trim afterwards as well. It is used instead of a
    pydantic constraint because a length violation there would fail validation
    and spend a whole extra generation on the retry.
    """
    schema_json = json.dumps(
        asked_schema(schema, hide=hide, limits=limits, scalars=scalars), indent=2
    )
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


_TOOL_CALL_CORRECTION = (
    "You called {names} instead of answering. No tool will run: the retrieval "
    "is finished and that call was discarded. Reply with ONLY the JSON object."
)


def _called(reply: BaseMessage) -> list[str]:
    """Tool names ``reply`` asked for instead of answering.

    A model that answers a schema request with a tool call leaves no content
    behind, so validation reports `EOF while parsing a value` — which describes
    the symptom and not the mistake. Feeding that back asks the model to fix
    JSON it never wrote, and it obliges by calling the tool again: on one
    comparison run the same call came back three times, failed the node, and
    cost the turn 1,861s against the 465s it takes when the first reply parses.
    """
    return [
        name
        for call in (getattr(reply, "tool_calls", None) or [])
        if (name := call.get("name"))
    ]


def constrain_json() -> bool:
    """Whether to hand the server the schema as a decoding constraint.

    **Off by default, because it was measured making the report worse.** The
    idea was sound and the result was not: a grammar cannot make the model write
    less — it still emits every brace and key, and Ollama's sampler has no
    jump-ahead — so the only thing it could buy was the retry a malformed object
    costs. What it actually bought, on the same 66k-character transcript and the
    same schema, against qwen3.8:27b:

        format on    5,483 chars   102.5s   0 of 5 candidates named a sku_code
        format off   7,299 chars    78.0s   5 of 5 named a sku_code and a family

    Every optional field went missing under the constraint. `sku_code` and
    `family` are `anyOf: [string, null]` and absent from `required`, so omitting
    them is legal, and constrained sampling took that path on every candidate in
    the shortlist — a report the gate rejects outright. It also misapplied
    `cite` to a judgement finding the unconstrained run wrote as prose. And it
    was slower per token, not faster: roughly 13 tok/s against 23.

    It does coexist with bound tools, which was the open question — Ollama
    accepted both together and parsed first time. That part works. Everything
    else about it was a loss, so `CS_STRUCTURED_FORMAT=1` turns it back on for
    anyone who wants to retest against a different model or server.
    """
    return (os.getenv("CS_STRUCTURED_FORMAT") or "0").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _takes_format(model: object) -> bool:
    """Whether this provider understands `format` as a decoding constraint.

    It is Ollama's, and the same node runs against a hosted endpoint in other
    configurations — `nodes.agent` resolves to an Anthropic model as shipped.
    Binding it there would put an unknown key in the request body and fail the
    call, so the constraint is applied where it means something and skipped
    where it does not.
    """
    return type(model).__name__.endswith("ChatOllama")


def structured(
    node: str,
    messages: list[BaseMessage],
    schema: type[T],
    attempts: int = 2,
    tools: list[object] | None = None,
    label: str | None = None,
    format_schema: dict | None = None,
) -> T:
    """Ask for a schema-shaped JSON object, validating and retrying.

    ``tools`` are bound but never expected to be called. It exists for a caller
    continuing a tool-using conversation: a server renders the tool schema into
    the prompt prefix, so asking the same messages *without* tools is a
    different prefix and re-reads the whole transcript from cold — measured at
    808 tok/s against 91,611 tok/s for the identical text with tools bound.
    Keeping them in front of the model is a standing invitation to call one
    instead of answering, so a reply that does costs the retry its cheap
    prefix: the tools come off and the transcript is re-read — see `_called`.

    ``label`` streams the JSON to screen as it is generated, under that name.
    The specialist report is the largest single generation in a turn, and it is
    otherwise invisible until it is finished.

    ``format_schema`` is the document to constrain the decode with. Pass the one
    the *prompt* was built from — a caller that hides fields must hide them in
    both or the grammar will demand what the instruction never mentioned.
    """
    bare = get_model(node)
    model = bare
    tool_names: set[str] | None = None
    if tools:
        model = bare.bind_tools(tools)
        # Bound for the prompt prefix, never meant to be called — but the model
        # sometimes calls one anyway, and a streamed parse can mangle the name.
        tool_names = {
            name for tool in tools if (name := getattr(tool, "name", None))
        }
    if format_schema and constrain_json() and _takes_format(bare):
        model = model.bind(format=format_schema)
    msgs: list[BaseMessage] = list(messages)
    has_schema_hint = any(
        isinstance(m, (SystemMessage, HumanMessage))
        and "JSON Schema" in (m.content if isinstance(m.content, str) else "")
        for m in msgs
    )
    if not has_schema_hint:
        msgs = [SystemMessage(content=schema_instruction(schema))] + msgs

    last_raw: str | None = None
    for attempt in range(attempts + 1):
        shown = label if attempt == 0 else f"{label} retry {attempt}"
        reply, _ = generate(
            model, msgs, label=shown if label else None, tool_names=tool_names
        )
        raw = _content_text(reply.content)
        last_raw = raw
        try:
            return schema.model_validate_json(strip_fences(raw))
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            called = _called(reply)
            if not called:
                msgs = msgs + [
                    AIMessage(content=raw),
                    HumanMessage(content=f"Invalid output. Fix these errors:\n{e}"),
                ]
                continue
            if trace := active_trace():
                trace.event(
                    "llm.structured_tool_call",
                    node=node,
                    label=label,
                    attempt=attempt,
                    tool_calls=called,
                )
            # Take the tools away rather than ask again with them in place. A
            # reply cannot be a tool call if no tool is bound, and asking twice
            # does not work: across three observed turns the model repeated the
            # same call every time it was told not to make it. The correction
            # still goes in — it accounts for the empty turn — but the binding
            # is what settles it. The cost is a changed prompt prefix and so a
            # cold re-read of the transcript, which is cheaper than the wasted
            # generation that precedes the same re-read one attempt later.
            model, tool_names = bare, None
            msgs = msgs + [HumanMessage(content=_TOOL_CALL_CORRECTION.format(
                names=", ".join(called)
            ))]
    raise StructuredOutputError(node, last_raw=last_raw)
