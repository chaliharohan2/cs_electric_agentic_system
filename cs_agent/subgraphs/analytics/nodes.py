"""Nodes for natural-language catalogue analytics."""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from cs_agent.llm import structured
from cs_agent.tools.impl import backend


class AnalyticsState(TypedDict):
    question: str
    sql: str
    result: dict[str, Any]
    answer: dict[str, Any]


class SQLQuery(BaseModel):
    sql: str = Field(description="A single read-only SQLite SELECT query.")


SCHEMA = """
families(family_id TEXT, category TEXT, name TEXT, summary TEXT)
variants(variant_id TEXT, family_id TEXT)
facts(family_id TEXT, canonical_fact_id TEXT, value_num REAL,
      value_text TEXT, unit TEXT, conditions_json TEXT)
""".strip()


def write_sql(state: AnalyticsState) -> dict[str, str]:
    query = structured(
        "analytics",
        [
            SystemMessage(
                content=(
                    "Translate the question into exactly one read-only SQLite SELECT. "
                    "Never modify data. Use only this schema:\n" + SCHEMA
                )
            ),
            HumanMessage(content=state["question"]),
        ],
        SQLQuery,
    )
    return {"sql": query.sql}


def execute_sql(state: AnalyticsState) -> dict[str, dict[str, Any]]:
    return {"result": backend().execute_sql(state["sql"])}


def shape(state: AnalyticsState) -> dict[str, dict[str, Any]]:
    result = state["result"]
    if "error" in result:
        return {"answer": {"error": result["error"], "sql": state["sql"]}}
    return {
        "answer": {
            "question": state["question"],
            "sql": state["sql"],
            "columns": result["columns"],
            "rows": result["rows"],
        }
    }
