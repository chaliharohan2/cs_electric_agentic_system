"""Shared LangGraph state."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class Evidence(TypedDict):
    tool: str
    family_id: str | None
    canonical_fact_id: str | None
    value_num: float | None
    value_text: str | None
    unit: str | None
    conditions: dict
    doc: str | None
    page: int | None


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: dict | None
    evidence: Annotated[list[Evidence], operator.add]
    clarify_count: int
    tool_calls_made: int
    assumptions: list[str]
    draft: str | None
    validation: dict | None
