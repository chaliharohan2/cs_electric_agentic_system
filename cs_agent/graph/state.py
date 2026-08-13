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
    agent: str
    brochure_md: str | None
    pricelist_pdf: str | None
    pricelist_page: int | None


def merge_reports(
    current: dict[str, dict[str, Any]], update: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    if "__reset__" in (update or {}):
        return {key: value for key, value in update.items() if key != "__reset__"}
    return {**(current or {}), **(update or {})}


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    session: dict[str, Any]
    standalone_question: str
    referenced_skus: list[str]
    is_followup: bool
    plan: dict | None
    dispatch: list[dict[str, Any]]
    brief: dict[str, Any]
    reports: Annotated[dict[str, dict[str, Any]], merge_reports]
    evidence: Annotated[list[Evidence], operator.add]
    clarify_count: int
    tool_calls_made: Annotated[int, operator.add]
    turn_tool_calls_start: int
    tool_failures: int
    revision_round: int
    gate_retries: int
    gate_result: dict[str, Any] | None
    sufficiency: dict[str, Any] | None
    assumptions: list[str]
    draft: str | None
    validation: dict | None
