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


def latest_stage(current: int | None, update: int | None) -> int:
    """Take the stage a branch reports, ignoring a write that carries none.

    Every specialist in a stage finishes by writing the same number, so
    last-write-wins is unambiguous under the parallel fan-out — and unlike a
    max reducer it lets a new turn reset the pipeline to stage zero.
    """
    if update is None:
        return current or 0
    return update


def merge_reports(
    current: dict[str, dict[str, Any]], update: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    if "__reset__" in (update or {}):
        return {key: value for key, value in update.items() if key != "__reset__"}
    return {**(current or {}), **(update or {})}


def merge_transcripts(
    current: dict[str, list[AnyMessage]] | None,
    update: dict[str, list[AnyMessage]] | None,
) -> dict[str, list[AnyMessage]]:
    """Last transcript per agent wins, and a new turn clears the previous one.

    Same reset protocol as `merge_reports`: a specialist that runs twice in a
    turn replaces its own entry rather than accumulating, so a retry always
    resumes from the most recent attempt.
    """
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
    upstream: dict[str, dict[str, Any]]
    # Set on a retry's Send payload only; the branch hands it to the specialist.
    prior_messages: list[AnyMessage]
    stage_index: Annotated[int, latest_stage]
    reports: Annotated[dict[str, dict[str, Any]], merge_reports]
    # Each specialist's finished transcript, so a gate retry can re-enter on the
    # work it already did instead of starting from an empty message list.
    transcripts: Annotated[dict[str, list[AnyMessage]], merge_transcripts]
    evidence: Annotated[list[Evidence], operator.add]
    clarify_count: int
    tool_calls_made: Annotated[int, operator.add]
    turn_tool_calls_start: int
    tool_failures: int
    revision_round: int
    gate_retries: dict[str, int]
    gate_result: dict[str, Any] | None
    sufficiency: dict[str, Any] | None
    assumptions: list[str]
    draft: str | None
    # Set when compose_final already printed the answer as it generated it,
    # so the caller does not print it a second time.
    draft_streamed: bool
    validation: dict | None
