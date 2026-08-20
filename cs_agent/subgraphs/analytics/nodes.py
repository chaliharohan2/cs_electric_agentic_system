"""Nodes and the private SQL tool for catalogue analytics."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from cs_agent.backends.read_only_sql import read_only_sql_error
from cs_agent.config.limits import get_limits
from cs_agent.llm import get_model, structured
from cs_agent.tool_errors import (
    TOOL_FAILURE_LIMIT,
    count_failures,
    trailing_tool_messages,
)
from cs_agent.tools.impl import backend

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
WRITE_SQL_PROMPT = (PROMPTS / "analytics_write_sql.md").read_text(encoding="utf-8")
SHAPE_PROMPT = (PROMPTS / "analytics_shape.md").read_text(encoding="utf-8")

logger = logging.getLogger(__name__)


class AnalyticsState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    question: str
    output_shape: str
    family: str | None
    spec_registry: list[dict[str, Any]]
    registry_note: str
    answer: dict[str, Any]
    query_count: int
    max_queries: int
    query_failures: int


class AnalyticsEvidence(BaseModel):
    statement: str = Field(
        description="A factual statement directly supported by a query result."
    )
    value_num: float | None = Field(
        default=None,
        description="The unformatted numeric value in the statement, if it has one.",
    )
    value_display: str | None = Field(
        default=None, description="The value as it should be displayed."
    )
    unit: str | None = None
    sku_code: str | None = None
    spec_id: str | None = None


class AnalyticsReport(BaseModel):
    summary: str = Field(
        description="A concise factual synthesis answering the delegated question."
    )
    evidence: list[AnalyticsEvidence] = Field(default_factory=list)
    queries_run: int = 0
    limitations: list[str] = Field(default_factory=list)
    error: str | None = None


def _registry_rows(rows: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    """Keep the most useful specs that fit a character budget.

    Canonical specs come first because they are the ones comparable across
    families, then the widest-coverage specs, because a spec held by three SKUs
    is rarely what a catalogue-wide question is about.
    """
    ordered = sorted(
        rows,
        key=lambda row: (
            not row.get("is_canonical_spec"),
            -(row.get("sku_count") or 0),
            row.get("spec_id") or "",
        ),
    )
    kept: list[dict[str, Any]] = []
    used = 0
    for row in ordered:
        size = len(json.dumps(row, default=str))
        if used + size > budget and kept:
            break
        kept.append(row)
        used += size
    return kept


def prepare(state: AnalyticsState) -> dict[str, Any]:
    """Load only the slice of the spec registry this question can use.

    The unscoped registry is one row per (family, spec_id) — 1,712 rows and
    roughly 108k tokens on the current catalogue, which alone overruns the
    80k window both Ollama profiles run. The analyst has SQL, so it can always
    discover what it is missing; what it needs injected is a starting
    vocabulary, not the whole thing.
    """
    limits = get_limits()
    family = state.get("family")
    # The flat rows, not the tool's grouped intersection: this budgets its own
    # starting vocabulary and wants one record per (family, spec_id).
    rows = backend().spec_rows(**({"family": family} if family else {}))
    total = len(rows)
    kept = _registry_rows(rows, limits.analytics_registry_chars)
    if family:
        scope = f"specs recorded for families matching {family!r}"
    else:
        scope = "specs across the whole catalogue"
    note = f"Showing {len(kept)} of {total} {scope}."
    if len(kept) < total:
        note += (
            " The list is truncated to the most widely used specs. It is a"
            " starting vocabulary, not the full set: query"
            " SELECT DISTINCT spec_id, spec_label, unit, value_kind FROM sku_fact"
            " WHERE ... to find any spec that is not listed here."
        )
    return {
        "spec_registry": kept,
        "registry_note": note,
        "query_count": state.get("query_count", 0),
        "query_failures": state.get("query_failures", 0),
    }


def execute_analytics_sql(sql: str) -> dict[str, Any]:
    """Execute one read-only SQLite query against the analytics views."""
    statement = sql.strip().rstrip(";")
    error = read_only_sql_error(statement)
    if error:
        return {"error": error}
    logger.info("analytics SQL: %s", statement)
    return backend().execute_sql(statement)


ANALYTICS_TOOLS = [
    StructuredTool.from_function(
        func=execute_analytics_sql,
        name="execute_analytics_sql",
        description=(
            "Execute one read-only SQLite query and return its columns, rows, "
            "row count, or database error. The statement may be a SELECT or a "
            "WITH ... SELECT; run as many as the budget allows, one per call."
        ),
    )
]


def _budget_note(state: AnalyticsState) -> str:
    remaining = max(0, state.get("max_queries", 0) - state.get("query_count", 0))
    return (
        f"Queries already executed: {state.get('query_count', 0)}."
        f"\nQueries remaining: {remaining}."
        f"\nFailed queries: {state.get('query_failures', 0)} of "
        f"{TOOL_FAILURE_LIMIT} allowed."
    )


def analyst(state: AnalyticsState) -> dict[str, list[AnyMessage]]:
    system = WRITE_SQL_PROMPT.format(
        spec_registry=json.dumps(state.get("spec_registry", []), indent=2),
        registry_note=state.get("registry_note", ""),
    )
    # Counters trail the history so the prompt prefix stays byte-identical across
    # turns; see the note in cs_agent/subgraphs/agents/nodes.py.
    response = (
        get_model("analytics.write_sql")
        .bind_tools(ANALYTICS_TOOLS)
        .invoke(
            [
                SystemMessage(content=system),
                *state.get("messages", []),
                HumanMessage(content=_budget_note(state)),
            ]
        )
    )
    return {"messages": [response]}


def record_queries(state: AnalyticsState) -> dict[str, int]:
    results = trailing_tool_messages(state.get("messages"))
    return {
        "query_count": state.get("query_count", 0) + len(results),
        "query_failures": state.get("query_failures", 0) + count_failures(results),
    }


def _transcript(messages: list[AnyMessage]) -> list[dict[str, Any]]:
    rendered: list[dict[str, Any]] = []
    for message in messages:
        item: dict[str, Any] = {"type": message.type, "content": message.content}
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            item["tool_calls"] = tool_calls
        rendered.append(item)
    return rendered


def summarize(state: AnalyticsState) -> dict[str, dict[str, Any]]:
    payload = {
        "question": state["question"],
        "output_shape": state.get("output_shape"),
        "queries_run": state.get("query_count", 0),
        "failed_queries": state.get("query_failures", 0),
        "analysis_transcript": _transcript(state.get("messages", [])),
    }
    report = structured(
        "analytics.shape",
        [
            SystemMessage(content=SHAPE_PROMPT),
            HumanMessage(content=json.dumps(payload, default=str)),
        ],
        AnalyticsReport,
    )
    report.queries_run = state.get("query_count", 0)
    return {"answer": report.model_dump()}
