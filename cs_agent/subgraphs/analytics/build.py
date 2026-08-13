"""Compile the analytics subgraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .nodes import (
    ANALYTICS_TOOLS,
    AnalyticsState,
    analyst,
    prepare,
    record_queries,
    summarize,
)


def _after_analyst(state: AnalyticsState) -> str:
    messages = state.get("messages", [])
    calls = getattr(messages[-1], "tool_calls", []) if messages else []
    remaining = state.get("max_queries", 0) - state.get("query_count", 0)
    if calls and len(calls) <= remaining:
        return "query"
    return "summarize"


def _after_record(state: AnalyticsState) -> str:
    if state.get("query_count", 0) >= state.get("max_queries", 0):
        return "summarize"
    return "analyst"


def build_analytics_graph():
    graph = StateGraph(AnalyticsState)
    graph.add_node("prepare", prepare)
    graph.add_node("analyst", analyst)
    graph.add_node("query", ToolNode(ANALYTICS_TOOLS))
    graph.add_node("record_queries", record_queries)
    graph.add_node("summarize", summarize)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "analyst")
    graph.add_conditional_edges("analyst", _after_analyst)
    graph.add_edge("query", "record_queries")
    graph.add_conditional_edges("record_queries", _after_record)
    graph.add_edge("summarize", END)
    return graph.compile()
