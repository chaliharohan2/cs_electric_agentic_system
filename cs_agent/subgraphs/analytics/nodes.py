"""Nodes and the private SQL tool for catalogue analytics."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

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
_READ_ONLY_SELECT = re.compile(r"^\s*select\b", re.IGNORECASE)


class AnalyticsState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    question: str
    output_shape: str
    spec_registry: list[dict[str, Any]]
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


def prepare(state: AnalyticsState) -> dict[str, Any]:
    return {
        "spec_registry": backend().list_canonical_specs(),
        "query_count": state.get("query_count", 0),
        "query_failures": state.get("query_failures", 0),
    }


def execute_analytics_sql(sql: str) -> dict[str, Any]:
    """Execute one read-only PostgreSQL SELECT against the analytics views."""
    statement = sql.strip().rstrip(";")
    if not _READ_ONLY_SELECT.match(statement) or ";" in statement:
        return {"error": "Only one read-only SELECT statement is allowed."}
    logger.info("analytics SQL: %s", statement)
    return backend().execute_sql(statement)


ANALYTICS_TOOLS = [
    StructuredTool.from_function(
        func=execute_analytics_sql,
        name="execute_analytics_sql",
        description=(
            "Execute one read-only PostgreSQL SELECT and return its columns, rows, "
            "row count, or database error. Use one call at a time."
        ),
    )
]


def analyst(state: AnalyticsState) -> dict[str, list[AnyMessage]]:
    remaining = max(0, state.get("max_queries", 0) - state.get("query_count", 0))
    failures = state.get("query_failures", 0)
    system = WRITE_SQL_PROMPT.format(
        spec_registry=json.dumps(state.get("spec_registry", []), indent=2)
    )
    system += (
        f"\n\nQueries already executed: {state.get('query_count', 0)}."
        f"\nQueries remaining: {remaining}."
        f"\nFailed queries: {failures} of {TOOL_FAILURE_LIMIT} allowed."
    )
    response = (
        get_model("analytics.write_sql")
        .bind_tools(ANALYTICS_TOOLS)
        .invoke([SystemMessage(content=system), *state.get("messages", [])])
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
