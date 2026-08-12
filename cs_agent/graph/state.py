"""Shared LangGraph state."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class Evidence(TypedDict):
    tool: str
    sku_code: str | None
    spec_id: str | None
    value_num: float | None
    value_min: float | None
    value_max: float | None
    value_display: str | None
    value_kind: str | None
    unit: str | None
    source_of_truth: str | None
    text: str | None


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: dict | None
    evidence: Annotated[list[Evidence], operator.add]
    clarify_count: int
    tool_calls_made: int
    assumptions: list[str]
    draft: str | None
    validation: dict | None
