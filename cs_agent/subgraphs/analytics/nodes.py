"""Nodes for natural-language catalogue analytics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from cs_agent.llm import structured
from cs_agent.tools.impl import backend

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
WRITE_SQL_PROMPT = (PROMPTS / "analytics_write_sql.md").read_text(encoding="utf-8")
SHAPE_PROMPT = (PROMPTS / "analytics_shape.md").read_text(encoding="utf-8")

SCHEMA = """
families(family_id TEXT, category TEXT, name TEXT, summary TEXT)
variants(variant_id TEXT, family_id TEXT)
facts(family_id TEXT, canonical_fact_id TEXT, value_num REAL,
      value_text TEXT, unit TEXT, conditions_json TEXT)
""".strip()


class AnalyticsState(TypedDict, total=False):
    question: str
    scope: dict | None
    output_shape: str
    sql: str
    result: dict[str, Any]
    answer: dict[str, Any]


class SQLQuery(BaseModel):
    sql: str = Field(description="A single read-only SELECT query.")


class ShapedAnswer(BaseModel):
    table: list[dict[str, Any]] = Field(default_factory=list)
    note: str = Field(
        description="One-line note stating what was excluded and why."
    )


def write_sql(state: AnalyticsState) -> dict[str, str]:
    fact_registry = backend().list_canonical_facts(None)
    prompt = WRITE_SQL_PROMPT.format(
        schema_ddl=SCHEMA,
        fact_registry=json.dumps(fact_registry, indent=2),
    )
    scope = state.get("scope")
    human = (
        f"Question: {state['question']}\n"
        f"Output shape: {state.get('output_shape') or 'tabular result'}\n"
        f"Scope: {json.dumps(scope) if scope else 'none'}\n"
        "Dialect note: the fixtures backend executes SQLite-compatible SELECT."
    )
    query = structured(
        "analytics.write_sql",
        [SystemMessage(content=prompt), HumanMessage(content=human)],
        SQLQuery,
    )
    return {"sql": query.sql}


def execute_sql(state: AnalyticsState) -> dict[str, dict[str, Any]]:
    return {"result": backend().execute_sql(state["sql"])}


def shape(state: AnalyticsState) -> dict[str, dict[str, Any]]:
    result = state["result"]
    if "error" in result:
        return {
            "answer": {
                "error": result["error"],
                "sql": state.get("sql"),
                "table": [],
                "note": "Query failed; no rows returned.",
            }
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
    return {
        "answer": {
            "question": state["question"],
            "sql": state.get("sql"),
            "table": shaped.table,
            "note": shaped.note,
            "columns": result.get("columns", []),
            "rows": result.get("rows", []),
        }
    }
