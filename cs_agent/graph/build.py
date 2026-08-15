"""Build the bounded product-agent graph."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from cs_agent.config.limits import get_limits
from cs_agent.contracts import REPORT_SCHEMAS
from cs_agent.graph.nodes import (
    clarify,
    compose_final,
    composer_sufficiency,
    gate,
    intake,
    planner,
)
from cs_agent.graph.state import AgentState
from cs_agent.observability import TraceLogger, agent_scoped_config
from cs_agent.subgraphs.agents import build_specialist_graph


def _after_planner(state: AgentState):
    plan = state.get("plan") or {}
    if (
        plan.get("needs_clarification")
        and state.get("clarify_count", 0) < get_limits().clarify_rounds
    ):
        return "clarify"
    question = state.get("standalone_question", "")
    resolved = (state.get("session") or {}).get("resolved_params") or {}
    known = {**resolved, **(plan.get("known_params") or {})}
    sends = []
    for brief in state.get("dispatch", []):
        merged = {**brief, "parameters": {**known, **(brief.get("parameters") or {})}}
        sends.append(
            Send("specialist", {"brief": merged, "standalone_question": question})
        )
    return sends


def _run_specialist(state: AgentState) -> dict[str, Any]:
    brief = state["brief"]
    agent_name = brief["agent"]
    try:
        result = build_specialist_graph(agent_name).invoke(
            {
                "brief": brief,
                "question": state.get("standalone_question", ""),
                "messages": [],
                "evidence": [],
            },
            config=agent_scoped_config(agent_name),
        )
    except Exception as exc:
        report = REPORT_SCHEMAS[agent_name](
            agent=agent_name,
            status="partial",
            summary=f"Specialist stopped after a runtime error: {exc}",
            gaps=[f"{type(exc).__name__}: {exc}"],
        ).model_dump()
        return {
            "reports": {agent_name: report},
            "evidence": [],
            "tool_calls_made": 0,
        }
    report = result["report"]
    return {
        "reports": {agent_name: report},
        "evidence": result.get("evidence", []),
        "tool_calls_made": int(report.get("tool_calls_used", 0)),
    }


def _after_gate(state: AgentState):
    result = state.get("gate_result") or {}
    failures = result.get("failures") or []
    if failures and state.get("gate_retries", 0) <= 1:
        briefs = {brief["agent"]: brief for brief in state.get("dispatch", [])}
        used = state.get("tool_calls_made", 0) - state.get("turn_tool_calls_start", 0)
        remaining = max(0, get_limits().global_tool_budget - used)
        allowance = min(
            get_limits().per_agent_tool_budget,
            remaining // max(1, len(failures)),
        )
        if allowance:
            return [
                Send(
                    "specialist",
                    {
                        "brief": {
                            **briefs[item["agent"]],
                            "allowance": allowance,
                            "revision_note": "; ".join(item["violations"]),
                        },
                        "standalone_question": state.get("standalone_question", ""),
                    },
                )
                for item in failures
            ]
    return "composer"


def _after_composer(state: AgentState):
    sufficiency = state.get("sufficiency") or {}
    gaps = sufficiency.get("gaps") or []
    limits = get_limits()
    if (
        sufficiency.get("revision_allowed", False)
        and gaps
    ):
        used = state.get("tool_calls_made", 0) - state.get("turn_tool_calls_start", 0)
        remaining = max(0, limits.global_tool_budget - used)
        allowance = min(limits.per_agent_tool_budget, remaining // len(gaps))
        if allowance:
            originals = {
                brief["agent"]: brief for brief in state.get("dispatch", [])
            }
            sends = []
            for gap in gaps:
                original = originals.get(gap["agent"], {
                    "agent": gap["agent"],
                    "objective": gap["missing"],
                    "scope": [],
                    "parameters": {},
                    "must_return": [gap["missing"]],
                })
                sends.append(
                    Send(
                        "specialist",
                        {
                            "brief": {
                                **original,
                                "allowance": allowance,
                                "revision_note": gap["missing"],
                            },
                            "standalone_question": state.get(
                                "standalone_question", ""
                            ),
                        },
                    )
                )
            return sends
    return "compose_final"


def _node_agent(state: AgentState) -> str | None:
    """Name the specialist a fan-out branch is running, when there is one."""
    brief = state.get("brief")
    if isinstance(brief, dict):
        return brief.get("agent")
    return None


def _trace_node(
    name: str,
    node: Callable[..., Any] | Any,
    trace: TraceLogger,
    *,
    next_node: str | None = None,
) -> Callable[[AgentState, RunnableConfig], Any]:
    def traced(state: AgentState, config: RunnableConfig) -> Any:
        agent = _node_agent(state)
        trace.event("node.start", node=name, agent=agent)
        trace.event("state.snapshot", node=name, agent=agent, state=state)
        try:
            if hasattr(node, "invoke"):
                update = node.invoke(state, config=config)
            else:
                update = node(state)
        except BaseException as exc:
            trace.event("node.error", node=name, agent=agent, error=exc)
            raise
        trace.event("state.update", node=name, agent=agent, update=update)
        trace.event("node.end", node=name, agent=agent)
        if next_node:
            trace.event(
                "node.transition",
                from_node=name,
                to_node=next_node,
                agent=agent,
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
    nodes = {
        "intake": intake,
        "planner": planner,
        "clarify": clarify,
        "specialist": _run_specialist,
        "gate": gate,
        "composer": composer_sufficiency,
        "compose_final": compose_final,
    }
    for name, node in nodes.items():
        graph.add_node(name, _trace_node(name, node, trace) if trace else node)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "planner")
    graph.add_conditional_edges("planner", _after_planner)
    graph.add_edge("clarify", "planner")
    graph.add_edge("specialist", "gate")
    graph.add_conditional_edges("gate", _after_gate)
    graph.add_conditional_edges("composer", _after_composer)
    graph.add_edge("compose_final", END)
    return graph.compile(checkpointer=checkpointer)
