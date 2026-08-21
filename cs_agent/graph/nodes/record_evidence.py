"""Deterministically turn tool output into normalized evidence records."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from cs_agent.backends.payload_shape import merge_scope
from cs_agent.graph.state import AgentState, Evidence
from cs_agent.tool_errors import count_failures, trailing_tool_messages

# Decoded ordering-code axes state their unit as the key, e.g. {"ka": 50}.
_UNIT_BY_KEY = {
    "ka": "kA",
    "a": "A",
    "kv": "kV",
    "v": "V",
    "kw": "kW",
    "w": "W",
    "khz": "kHz",
    "hz": "Hz",
}


def _empty(tool: str) -> Evidence:
    return {
        "tool": tool,
        "sku_code": None,
        "spec_id": None,
        "value_num": None,
        "value_min": None,
        "value_max": None,
        "value_display": None,
        "value_kind": None,
        "unit": None,
        "source_of_truth": None,
        "text": None,
    }


def _fact_record(tool: str, fact: dict[str, Any], sku_code: str | None) -> Evidence:
    record = _empty(tool)
    record.update(
        {
            "sku_code": fact.get("sku_code", sku_code),
            "spec_id": fact.get("spec_id"),
            "value_num": fact.get("value_num"),
            "value_min": fact.get("value_min"),
            "value_max": fact.get("value_max"),
            "value_display": fact.get("value_display"),
            "value_kind": fact.get("value_kind"),
            "unit": fact.get("unit"),
            "source_of_truth": fact.get("source_of_truth"),
            # `fact_sentence` is no longer sent by `get_sku` or `product_search`,
            # so this is now None for a catalogue fact and the composer's
            # evidence row prints `text=null`. Nothing is lost: the sentence was
            # a template restating the label and the value, and the row already
            # prints the spec, the value, the unit and the source beside it.
            # The read stays because a payload that does carry one — an older
            # trace replayed, a backend that still writes it — should still use
            # it rather than silently drop it.
            "text": fact.get("fact_sentence"),
        }
    )
    return record


def _measurement(
    tool: str,
    value: Any,
    *,
    unit: str | None = None,
    spec_id: str | None = None,
    sku_code: str | None = None,
    text: str | None = None,
    source: str = "catalogue_index",
) -> Evidence | None:
    """A retrieved number the answer is allowed to quote."""
    if isinstance(value, str):
        # Axis meanings arrive as text: rating_idx "06" means the string "630".
        try:
            value = float(value.strip())
        except ValueError:
            return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    record = _empty(tool)
    record.update(
        {
            "sku_code": sku_code,
            "spec_id": spec_id,
            "value_num": float(value),
            "value_display": str(value),
            "value_kind": "scalar",
            "unit": unit,
            "source_of_truth": source,
            "text": text,
        }
    )
    return record


def _description(
    tool: str,
    value: Any,
    *,
    spec_id: str | None = None,
    sku_code: str | None = None,
    text: str | None = None,
    source: str = "code_grammar",
) -> Evidence | None:
    """A retrieved phrase carrying a figure, such as "MicroPro2 3.1 (LSIG)".

    A value that is nothing but a number belongs in a measurement record, where
    its unit can be stated and checked; keeping a bare copy here as free text
    would let the answer attach any unit it liked to the figure.
    """
    if not isinstance(value, str) or not any(char.isdigit() for char in value):
        return None
    try:
        float(value.strip())
    except ValueError:
        pass
    else:
        return None
    record = _empty(tool)
    record.update(
        {
            "sku_code": sku_code,
            "spec_id": spec_id,
            "value_display": value,
            "value_kind": "text",
            "source_of_truth": source,
            "text": text,
        }
    )
    return record


def _name(tool: str, value: Any) -> Evidence | None:
    """A catalogue name. Digits inside it are part of the name, not a claim."""
    if not isinstance(value, str) or not value.strip():
        return None
    record = _empty(tool)
    record.update(
        {
            "value_display": value.strip(),
            "value_kind": "name",
            "source_of_truth": "catalogue_index",
        }
    )
    return record


def _meaning_items(meaning: Any) -> Iterator[tuple[str, Any]]:
    """Flatten a decoded axis meaning, which may be a JSON object or a string."""
    if isinstance(meaning, str):
        stripped = meaning.strip()
        if not stripped.startswith("{"):
            yield "", stripped
            return
        try:
            meaning = json.loads(stripped)
        except json.JSONDecodeError:
            yield "", stripped
            return
    if isinstance(meaning, dict):
        for key, value in meaning.items():
            if isinstance(value, dict):
                yield from _meaning_items(value)
            else:
                yield str(key), value
    elif meaning is not None:
        yield "", meaning


def _axis_records(
    tool: str, axis: str, entry: dict[str, Any], scope: str
) -> Iterator[Evidence | None]:
    label = f"{scope} {axis} code {entry.get('code')}".strip()
    yield _measurement(tool, entry.get("sku_count"), text=f"SKU count for {label}")
    # Axis codes carry figures of their own: frame "1", poles "3P", rating "06".
    # A wholly numeric code is a figure the answer may quote when it tabulates
    # the axis; the rest stay descriptions.
    yield _measurement(
        tool, entry.get("code"), spec_id=axis, text=label, source="code_grammar"
    )
    yield _description(tool, entry.get("code"), spec_id=axis, text=label)
    for key, value in _meaning_items(entry.get("meaning")):
        yield _measurement(
            tool,
            value,
            unit=_UNIT_BY_KEY.get(key.lower()),
            spec_id=axis,
            text=label,
            source="code_grammar",
        )
        yield _description(tool, value, spec_id=axis, text=label)


def _catalogue_index(tool: str, payload: dict[str, Any]) -> Iterator[Evidence | None]:
    """Counts, observed bounds, and decoded axes are retrieved facts too.

    Without them the composer cannot safely quote a SKU count or a category's
    observed range, although both came straight from a tool. Only the
    catalogue-shape tools are indexed this way; doing it per SKU hit would add
    hundreds of near-duplicate rows to the composer's evidence table.
    """
    category = payload.get("category")
    spec_id = payload.get("spec_id")
    unit = payload.get("unit")
    scope = " ".join(
        str(part) for part in (category, payload.get("family")) if part
    )
    if spec_id:
        yield _measurement(
            tool,
            payload.get("sku_count"),
            spec_id=spec_id,
            text=f"SKUs carrying {spec_id} in {category}",
        )
        for bound in ("observed_min", "observed_max"):
            yield _measurement(
                tool,
                payload.get(bound),
                unit=unit,
                spec_id=spec_id,
                text=f"{spec_id} {bound} in {category}",
            )
    else:
        yield _measurement(
            tool, payload.get("sku_count"), text=f"SKU count for {scope}"
        )
    for key in ("categories", "families"):
        for row in payload.get(key) or []:
            if not isinstance(row, dict):
                continue
            name = row.get("family") or row.get("category")
            yield _measurement(
                tool, row.get("sku_count"), text=f"SKU count for {name}"
            )
            yield _name(tool, row.get("category"))
            yield _name(tool, row.get("family"))
    for name in payload.get("matched_families") or []:
        yield _name(tool, name)
    for axis, entries in (payload.get("axes") or {}).items():
        for entry in entries or []:
            if isinstance(entry, dict):
                yield from _axis_records(tool, axis, entry, scope)


def _deduplicated(records: Iterator[Evidence | None]) -> list[Evidence]:
    seen: set[tuple] = set()
    unique: list[Evidence] = []
    for record in records:
        if record is None:
            continue
        key = (
            record["sku_code"],
            record["spec_id"],
            record["value_num"],
            record["value_display"],
            record["unit"],
            record["value_kind"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def _search_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The SKU rows of a search result, flat or grouped.

    The payload's `scope` is merged back underneath each row, because
    `product_search` hoists `sku_code`-independent fields out of the hits when
    they all agree and a fact record wants them back.
    """
    rows = [row for row in payload.get("hits") or [] if isinstance(row, dict)]
    for group in payload.get("groups") or []:
        if isinstance(group, dict):
            rows.extend(
                row for row in group.get("sample_hits") or [] if isinstance(row, dict)
            )
    return [merge_scope(payload, row) for row in rows]


def _extract(payload: Any, tool: str, sku_code: str | None = None) -> list[Evidence]:
    if isinstance(payload, list):
        evidence: list[Evidence] = []
        for item in payload:
            evidence.extend(_extract(item, tool, sku_code))
        return evidence
    if not isinstance(payload, dict) or (
        payload.get("error") and tool != "analytics_query"
    ):
        return []
    if tool == "list_canonical_specs" and "specs" in payload:
        # The tool answers a multi-family scope now, so its rows arrive wrapped
        # in an envelope naming that scope. Index the rows, which are the same
        # per-(family, spec_id) records this used to be handed as a bare list.
        # Letting the envelope fall through to the generic path instead files
        # every spec *definition* as a SKU fact and replaces 150 quotable
        # counts and observed bounds with one 26,855-char blob.
        return _extract(payload["specs"], tool, sku_code)

    current_sku = payload.get("sku_code", sku_code)
    evidence: list[Evidence] = []
    evidence.extend(
        _deduplicated(_name(tool, payload.get(key)) for key in ("category", "family"))
    )
    for key in ("facts", "specs"):
        for fact in payload.get(key) or []:
            evidence.append(_fact_record(tool, fact, current_sku))
    for row in payload.get("rows") or []:
        for fact in row.get("facts", []) if isinstance(row, dict) else []:
            evidence.append(_fact_record(tool, fact, fact.get("sku_code")))
    # A `product_search` hangs its facts on the hits, not at the top level, so
    # reading `specs` alone saw none of them: a search with `return_specs`
    # returning three hits of three fully-formed facts each — `source_pdf` and
    # `source_page` included — produced zero evidence rows. That blinded every
    # consumer of this index at once. On one captured run, 16 of the 33 facts a
    # report cited could not be resolved against it, all of them from SKUs
    # reached by search rather than by `get_sku`.
    #
    # `groups[].sample_hits` is where a grouped search puts the same rows.
    for hit in _search_rows(payload):
        for fact in hit.get("specs") or []:
            if isinstance(fact, dict):
                evidence.append(
                    _fact_record(tool, fact, hit.get("sku_code") or current_sku)
                )
    if tool == "search_documents" and payload.get("text"):
        record = _empty(tool)
        record.update(
            {
                "sku_code": current_sku,
                "text": str(payload["text"]),
                "source_of_truth": "product_chunks.content",
            }
        )
        evidence.append(record)
    if tool in {"taxonomy_browse", "list_canonical_specs"}:
        record = _empty(tool)
        record["text"] = json.dumps(payload, sort_keys=True, default=str)
        evidence.append(record)
        evidence.extend(_deduplicated(_catalogue_index(tool, payload)))
    if tool == "analytics_query":
        for item in payload.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            record = _empty(tool)
            record.update(
                {
                    "sku_code": item.get("sku_code"),
                    "spec_id": item.get("spec_id"),
                    "value_num": item.get("value_num"),
                    "value_display": item.get("value_display"),
                    "value_kind": (
                        "scalar" if item.get("value_num") is not None else None
                    ),
                    "unit": item.get("unit"),
                    "source_of_truth": "analytics_query",
                    "text": item.get("statement"),
                }
            )
            evidence.append(record)
        for text in [
            payload.get("summary"),
            *(payload.get("limitations") or []),
        ]:
            if not text:
                continue
            record = _empty(tool)
            record["text"] = str(text)
            record["source_of_truth"] = "analytics_query"
            evidence.append(record)
    return evidence


def _collapse_names(records: list[Evidence]) -> list[Evidence]:
    """One record per catalogue name; every hit repeats its category and family."""
    seen: set[str] = set()
    kept: list[Evidence] = []
    for record in records:
        if record.get("value_kind") == "name":
            name = record.get("value_display") or ""
            if name in seen:
                continue
            seen.add(name)
        kept.append(record)
    return kept


def record_evidence(state: AgentState) -> dict[str, Any]:
    records: list[Evidence] = []
    results = trailing_tool_messages(state.get("messages"))
    for message in results:
        content = message.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        records.extend(_extract(content, message.name or "unknown"))
    # A failed call still consumes the call budget, so a tool erroring in a loop
    # cannot outlast it.
    return {
        "evidence": _collapse_names(records),
        "tool_calls_made": state.get("tool_calls_made", 0) + len(results),
        "tool_failures": state.get("tool_failures", 0) + count_failures(results),
    }
