"""Nodes for natural-language catalogue analytics."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from cs_agent.llm import get_model, structured
from cs_agent.llm.structured import strip_fences
from cs_agent.tools.impl import backend

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
WRITE_SQL_PROMPT = (PROMPTS / "analytics_write_sql.md").read_text(encoding="utf-8")
SHAPE_PROMPT = (PROMPTS / "analytics_shape.md").read_text(encoding="utf-8")

logger = logging.getLogger(__name__)


class AnalyticsState(TypedDict, total=False):
    question: str
    output_shape: str
    spec_registry: list[dict[str, Any]]
    sql: str
    result: dict[str, Any]
    answer: dict[str, Any]
    retries: int
    sql_error: str | None


class ShapedAnswer(BaseModel):
    table: list[dict[str, Any]] = Field(default_factory=list)
    note: str = Field(
        description="One-line note stating what was excluded and why."
    )


class SqlResult(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    sql: str = ""
    row_count: int = 0
    note: str = ""
    error: str | None = None


def plan_sql(state: AnalyticsState) -> dict[str, Any]:
    return {
        "spec_registry": backend().list_canonical_specs(None),
        "retries": state.get("retries", 0),
    }


def write_sql(state: AnalyticsState) -> dict[str, str]:
    prompt = WRITE_SQL_PROMPT.format(
        spec_registry=json.dumps(state.get("spec_registry", []), indent=2),
    )
    human = (
        f"Question: {state['question']}\n"
        f"Output shape: {state.get('output_shape') or 'tabular result'}"
    )
    if state.get("sql_error"):
        human += (
            "\nThe previous SQL failed. Correct it using this database error:\n"
            + str(state["sql_error"])
        )
    response = get_model("analytics.write_sql").invoke(
        [SystemMessage(content=prompt), HumanMessage(content=human)]
    )
    content = response.content
    text = content if isinstance(content, str) else str(content)
    statement = strip_fences(text).strip().rstrip(";")
    logger.info("analytics SQL: %s", statement)
    return {"sql": statement, "sql_error": None}


def execute_sql(state: AnalyticsState) -> dict[str, dict[str, Any]]:
    # GUARDRAIL_HOOK: add a read-only role, timeout, and row cap after the POC.
    result = backend().execute_sql(state["sql"])
    update: dict[str, Any] = {"result": result}
    if result.get("error"):
        update["sql_error"] = str(result["error"])
        update["retries"] = state.get("retries", 0) + 1
    return update


def shape(state: AnalyticsState) -> dict[str, dict[str, Any]]:
    result = state["result"]
    if "error" in result:
        answer = SqlResult(
            sql=state.get("sql", ""),
            note="Query failed; no rows returned.",
            error=result["error"],
        )
        return {
            "answer": answer.model_dump()
        }
    prompt = SHAPE_PROMPT
    payload = {
        "output_shape": state.get("output_shape"),
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
    }
    shaped = structured(
        "analytics.shape",
        [
            SystemMessage(content=prompt),
            HumanMessage(content=json.dumps(payload, default=str)),
        ],
        ShapedAnswer,
    )
    columns = list(result.get("columns", []))
    rows = result.get("rows", [])
    if shaped.table:
        columns = list(shaped.table[0])
        rows = [[row.get(column) for column in columns] for row in shaped.table]
    answer = SqlResult(
        columns=columns,
        rows=rows,
        sql=state.get("sql", ""),
        row_count=len(rows),
        note=shaped.note,
    )
    return {"answer": answer.model_dump()}
