"""Build the bounded product-agent graph."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
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
from cs_agent.observability import TraceLogger
from cs_agent.tools import TOOLS


def _after_planner(state: AgentState) -> Literal["clarify", "agent"]:
    plan = state.get("plan") or {}
    if plan.get("needs_clarification") and state.get("clarify_count", 0) < 2:
        return "clarify"
    return "agent"


def _after_agent(state: AgentState) -> Literal["tools", "composer"]:
    messages = state.get("messages", [])
    calls = getattr(messages[-1], "tool_calls", []) if messages else []
    # Do not dispatch a parallel batch that would exceed the hard budget.
    if calls and state.get("tool_calls_made", 0) + len(calls) <= 12:
        return "tools"
    return "composer"


def _after_validator(state: AgentState) -> Literal["composer", "__end__"]:
    validation = state.get("validation") or {}
    if not validation.get("passed") and validation.get("attempt", 0) < 2:
        return "composer"
    return END


def _trace_node(
    name: str,
    node: Callable[..., Any] | Any,
    trace: TraceLogger,
    *,
    next_node: str | None = None,
) -> Callable[[AgentState, RunnableConfig], Any]:
    def traced(state: AgentState, config: RunnableConfig) -> Any:
        trace.event("node.start", node=name)
        trace.event("state.snapshot", node=name, state=state)
        try:
            if hasattr(node, "invoke"):
                update = node.invoke(state, config=config)
            else:
                update = node(state)
        except BaseException as exc:
            trace.event("node.error", node=name, error=exc)
            raise
        trace.event("state.update", node=name, update=update)
        trace.event("node.end", node=name)
        if next_node:
            trace.event(
                "node.transition",
                from_node=name,
                to_node=next_node,
                transition_type="fixed",
            )
            trace.event("agent.change", from_agent=name, to_agent=next_node)
        return update

    return traced


def _trace_route(
    from_node: str,
    route: Callable[[AgentState], str],
    trace: TraceLogger,
) -> Callable[[AgentState], str]:
    def traced(state: AgentState) -> str:
        destination = route(state)
        trace.event(
            "node.transition",
            from_node=from_node,
            to_node=destination,
            transition_type="conditional",
        )
        trace.event(
            "agent.change",
            from_agent=from_node,
            to_agent=destination,
        )
        return destination

    return traced


def build_graph(checkpointer=None, trace: TraceLogger | None = None):
    graph = StateGraph(AgentState)
    tool_node = ToolNode(TOOLS)
    if trace is None:
        graph.add_node("planner", planner)
        graph.add_node("clarify", clarify)
        graph.add_node("agent", agent)
        graph.add_node("tools", tool_node)
        graph.add_node("record_evidence", record_evidence)
        graph.add_node("composer", composer)
        graph.add_node("validator", validator)
        after_planner = _after_planner
        after_agent = _after_agent
        after_validator = _after_validator
    else:
        graph.add_node("planner", _trace_node("planner", planner, trace))
        graph.add_node(
            "clarify", _trace_node("clarify", clarify, trace, next_node="planner")
        )
        graph.add_node("agent", _trace_node("agent", agent, trace))
        graph.add_node(
            "tools",
            _trace_node("tools", tool_node, trace, next_node="record_evidence"),
        )
        graph.add_node(
            "record_evidence",
            _trace_node(
                "record_evidence", record_evidence, trace, next_node="agent"
            ),
        )
        graph.add_node(
            "composer",
            _trace_node("composer", composer, trace, next_node="validator"),
        )
        graph.add_node("validator", _trace_node("validator", validator, trace))
        after_planner = _trace_route("planner", _after_planner, trace)
        after_agent = _trace_route("agent", _after_agent, trace)
        after_validator = _trace_route("validator", _after_validator, trace)

    graph.add_edge(START, "planner")
    graph.add_conditional_edges("planner", after_planner)
    graph.add_edge("clarify", "planner")
    graph.add_conditional_edges("agent", after_agent)
    graph.add_edge("tools", "record_evidence")
    graph.add_edge("record_evidence", "agent")
    graph.add_edge("composer", "validator")
    graph.add_conditional_edges("validator", after_validator)
    return graph.compile(checkpointer=checkpointer)
