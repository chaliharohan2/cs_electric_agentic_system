"""Compile the analytics subgraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import AnalyticsState, execute_sql, plan_sql, shape, write_sql


def _after_execute(state: AnalyticsState) -> str:
    if state.get("result", {}).get("error") and state.get("retries", 0) <= 2:
        return "write_sql"
    return "shape"


def build_analytics_graph():
    graph = StateGraph(AnalyticsState)
    graph.add_node("plan_sql", plan_sql)
    graph.add_node("write_sql", write_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("shape", shape)
    graph.add_edge(START, "plan_sql")
    graph.add_edge("plan_sql", "write_sql")
    graph.add_edge("write_sql", "execute_sql")
    graph.add_conditional_edges("execute_sql", _after_execute)
    graph.add_edge("shape", END)
    return graph.compile()
