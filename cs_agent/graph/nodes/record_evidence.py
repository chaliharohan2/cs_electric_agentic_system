"""Deterministically turn tool output into normalized evidence records."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import ToolMessage

from cs_agent.graph.state import AgentState, Evidence


def _empty(tool: str) -> Evidence:
    return {
        "tool": tool,
        "family_id": None,
        "canonical_fact_id": None,
        "value_num": None,
        "value_text": None,
        "unit": None,
        "conditions": {},
        "doc": None,
        "page": None,
    }


def _extract(payload: Any, tool: str, family_id: str | None = None) -> list[Evidence]:
    if isinstance(payload, list):
        evidence: list[Evidence] = []
        for item in payload:
            evidence.extend(_extract(item, tool, family_id))
        return evidence
    if not isinstance(payload, dict) or "error" in payload:
        return []

    current_family = payload.get("family_id", family_id)
    evidence = []
    if "facts" in payload:
        for fact in payload["facts"]:
            record = _empty(tool)
            record.update(
                {
                    "family_id": current_family,
                    "canonical_fact_id": fact.get("canonical_fact_id"),
                    "value_num": fact.get("value_num"),
                    "value_text": fact.get("value_text"),
                    "unit": fact.get("unit"),
                    "conditions": fact.get("conditions") or {},
                }
            )
            evidence.append(record)
    if "products" in payload:
        evidence.extend(_extract(payload["products"], tool))
    if "children" in payload:
        record = _empty(tool)
        record["value_text"] = json.dumps(payload, sort_keys=True, default=str)
        evidence.append(record)
    if {"doc", "page", "text"} <= payload.keys():
        record = _empty(tool)
        record.update(
            {
                "family_id": current_family,
                "value_text": payload["text"],
                "doc": payload["doc"],
                "page": payload["page"],
            }
        )
        evidence.append(record)
    if "table" in payload or "rows" in payload:
        rows = payload.get("table") or payload.get("rows") or []
        for row in rows:
            record = _empty(tool)
            record["value_text"] = json.dumps(row, sort_keys=True, default=str)
            record["doc"] = "analytics"
            evidence.append(record)
        if payload.get("note"):
            note = _empty(tool)
            note["value_text"] = str(payload["note"])
            note["doc"] = "analytics_note"
            evidence.append(note)
    return evidence


def record_evidence(state: AgentState) -> dict[str, list[Evidence]]:
    records: list[Evidence] = []
    for message in reversed(state.get("messages", [])):
        if not isinstance(message, ToolMessage):
            break
        content = message.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        records.extend(_extract(content, message.name or "unknown"))
    return {"evidence": list(reversed(records))}
