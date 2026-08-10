"""Build the bounded product-agent graph."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from cs_agent.graph.nodes import (
    agent,
    clarify,
    composer,
    planner,
    record_evidence,
    validator,
)
from cs_agent.graph.state import AgentState
from cs_agent.tools import TOOLS


def _after_planner(state: AgentState) -> Literal["clarify", "agent"]:
    plan = state.get("plan") or {}
    if plan.get("needs_clarification") and state.get("clarify_count", 0) < 2:
        return "clarify"
    return "agent"


def _after_agent(state: AgentState) -> Literal["tools", "composer"]:
    messages = state.get("messages", [])
    calls = getattr(messages[-1], "tool_calls", []) if messages else []
    if calls and state.get("tool_calls_made", 0) <= 12:
        return "tools"
    return "composer"


def _after_validator(state: AgentState) -> Literal["composer", "__end__"]:
    validation = state.get("validation") or {}
    if not validation.get("passed") and validation.get("attempt", 0) < 2:
        return "composer"
    return END


def build_graph(checkpointer=None):
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner)
    graph.add_node("clarify", clarify)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("record_evidence", record_evidence)
    graph.add_node("composer", composer)
    graph.add_node("validator", validator)

    graph.add_edge(START, "planner")
    graph.add_conditional_edges("planner", _after_planner)
    graph.add_edge("clarify", "planner")
    graph.add_conditional_edges("agent", _after_agent)
    graph.add_edge("tools", "record_evidence")
    graph.add_edge("record_evidence", "agent")
    graph.add_edge("composer", "validator")
    graph.add_conditional_edges("validator", _after_validator)
    return graph.compile(checkpointer=checkpointer)
