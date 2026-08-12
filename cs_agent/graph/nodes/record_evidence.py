"""Deterministically turn tool output into normalized evidence records."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import ToolMessage

from cs_agent.graph.state import AgentState, Evidence


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
            "text": fact.get("fact_sentence"),
        }
    )
    return record


def _extract(payload: Any, tool: str, sku_code: str | None = None) -> list[Evidence]:
    if isinstance(payload, list):
        evidence: list[Evidence] = []
        for item in payload:
            evidence.extend(_extract(item, tool, sku_code))
        return evidence
    if not isinstance(payload, dict) or "error" in payload:
        return []

    current_sku = payload.get("sku_code", sku_code)
    evidence: list[Evidence] = []
    for key in ("facts", "specs"):
        for fact in payload.get(key) or []:
            evidence.append(_fact_record(tool, fact, current_sku))
    for row in payload.get("rows") or []:
        for fact in row.get("facts", []) if isinstance(row, dict) else []:
            evidence.append(_fact_record(tool, fact, fact.get("sku_code")))
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
    if tool == "analytics_query":
        rows = payload.get("table") or payload.get("rows") or []
        for row in rows:
            values = row.values() if isinstance(row, dict) else row
            for value in values:
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    record = _empty(tool)
                    record["value_num"] = float(value)
                    record["value_display"] = str(value)
                    record["source_of_truth"] = "analytics_query"
                    record["text"] = json.dumps(row, sort_keys=True, default=str)
                    evidence.append(record)
        if payload.get("note"):
            note = _empty(tool)
            note["text"] = str(payload["note"])
            note["source_of_truth"] = "analytics_query"
            evidence.append(note)
    return evidence


def record_evidence(state: AgentState) -> dict[str, Any]:
    records: list[Evidence] = []
    completed_calls = 0
    for message in reversed(state.get("messages", [])):
        if not isinstance(message, ToolMessage):
            break
        completed_calls += 1
        content = message.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        records.extend(_extract(content, message.name or "unknown"))
    return {
        "evidence": list(reversed(records)),
        "tool_calls_made": state.get("tool_calls_made", 0) + completed_calls,
    }
