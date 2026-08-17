"""Build the bounded product-agent graph."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from cs_agent.config.limits import get_limits
from cs_agent.contracts import REPORT_SCHEMAS, brief_depth
from cs_agent.graph.digest import upstream_digest
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


def brief_stage(brief: dict[str, Any]) -> int:
    return int(brief.get("stage", 1) or 1)


def stages_in(dispatch: list[dict[str, Any]]) -> list[int]:
    """The stage numbers a plan uses, in execution order."""
    return sorted({brief_stage(brief) for brief in dispatch})


def briefs_for_stage(dispatch: list[dict[str, Any]], stage: int):
    return [brief for brief in dispatch if brief_stage(brief) == stage]


def next_stage(dispatch: list[dict[str, Any]], current: int) -> int | None:
    return next((stage for stage in stages_in(dispatch) if stage > current), None)


def _allowance(state: AgentState, count: int) -> int:
    """Split what is left of the turn's budget across one stage's agents.

    Allocating per stage rather than once up front means a later stage inherits
    whatever an earlier one did not spend, and a cheap first stage no longer
    reserves budget the pipeline never uses.
    """
    limits = get_limits()
    used = state.get("tool_calls_made", 0) - state.get("turn_tool_calls_start", 0)
    remaining = max(0, limits.global_tool_budget - used)
    return min(limits.per_agent_tool_budget, remaining // max(1, count))


def _known_params(state: AgentState) -> dict[str, Any]:
    plan = state.get("plan") or {}
    resolved = (state.get("session") or {}).get("resolved_params") or {}
    return {**resolved, **(plan.get("known_params") or {})}


def _send(
    state: AgentState,
    brief: dict[str, Any],
    stage: int,
    allowance: int,
    upstream: dict[str, Any],
    *,
    revision_note: str | None = None,
    resume: bool = False,
) -> Send:
    known = _known_params(state)
    depth = brief_depth(brief)
    if depth == "overview":
        # Capping here rather than in _allowance keeps the fair share of the
        # turn's budget one calculation, and applies the ceiling on every path
        # that reaches a specialist: first dispatch, gate retry, and revision.
        allowance = min(allowance, get_limits().overview_tool_budget)
    merged = {
        **brief,
        "stage": stage,
        "allowance": allowance,
        "depth": depth,
        "parameters": {**known, **(brief.get("parameters") or {})},
    }
    if revision_note:
        merged["revision_note"] = revision_note
    payload: dict[str, Any] = {
        "brief": merged,
        "standalone_question": state.get("standalone_question", ""),
        "upstream": upstream,
    }
    if resume:
        prior = (state.get("transcripts") or {}).get(brief["agent"]) or []
        if prior:
            payload["prior_messages"] = prior
    return Send("specialist", payload)


def dispatch_stage(state: AgentState, stage: int) -> list[Send]:
    """Fan out one stage, handing it the digests of every stage before it."""
    briefs = briefs_for_stage(state.get("dispatch", []), stage)
    allowance = _allowance(state, len(briefs))
    if not briefs or not allowance:
        return []
    upstream = upstream_digest(
        state.get("reports", {}), state.get("dispatch", []), stage
    )
    return [_send(state, brief, stage, allowance, upstream) for brief in briefs]


def _run_specialist(state: AgentState) -> dict[str, Any]:
    brief = state["brief"]
    agent_name = brief["agent"]
    stage = brief_stage(brief)
    try:
        result = build_specialist_graph(agent_name).invoke(
            {
                "brief": brief,
                "question": state.get("standalone_question", ""),
                "upstream": state.get("upstream") or {},
                "prior_messages": state.get("prior_messages") or [],
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
            "stage_index": stage,
        }
    report = result["report"]
    return {
        "reports": {agent_name: report},
        # Kept so a gate retry can resume here rather than re-retrieve; see
        # `_resume_messages`. Held for the turn only — run.py resets it.
        "transcripts": {agent_name: result.get("messages", [])},
        "evidence": result.get("evidence", []),
        "tool_calls_made": int(report.get("tool_calls_used", 0)),
        "stage_index": stage,
    }


def _after_planner(state: AgentState):
    plan = state.get("plan") or {}
    if (
        plan.get("needs_clarification")
        and state.get("clarify_count", 0) < get_limits().clarify_rounds
    ):
        return "clarify"
    stages = stages_in(state.get("dispatch", []))
    if stages and (sends := dispatch_stage(state, stages[0])):
        return sends
    return "composer"


def _after_gate(state: AgentState):
    """Retry this stage's failures, else start the next stage, else compose."""
    stage = int(state.get("stage_index", 1) or 1)
    result = state.get("gate_result") or {}
    failures = result.get("failures") or []
    retries = (state.get("gate_retries") or {}).get(str(stage), 0)
    if failures and retries <= 1:
        briefs = {brief["agent"]: brief for brief in state.get("dispatch", [])}
        allowance = _allowance(state, len(failures))
        if allowance:
            upstream = upstream_digest(
                state.get("reports", {}), state.get("dispatch", []), stage
            )
            retry = [
                _send(
                    state,
                    briefs[item["agent"]],
                    stage,
                    allowance,
                    upstream,
                    revision_note="; ".join(item["violations"]),
                    resume=True,
                )
                for item in failures
                if item["agent"] in briefs
            ]
            if retry:
                return retry
    following = next_stage(state.get("dispatch", []), stage)
    if following is not None and (sends := dispatch_stage(state, following)):
        return sends
    return "composer"


def _after_composer(state: AgentState):
    sufficiency = state.get("sufficiency") or {}
    gaps = sufficiency.get("gaps") or []
    if sufficiency.get("revision_allowed", False) and gaps:
        stage = int(state.get("stage_index", 1) or 1)
        allowance = _allowance(state, len(gaps))
        if allowance:
            dispatch = state.get("dispatch", [])
            originals = {brief["agent"]: brief for brief in dispatch}
            sends = []
            for gap in gaps:
                original = originals.get(gap["agent"], {
                    "agent": gap["agent"],
                    "objective": gap["missing"],
                    "scope": [],
                    "parameters": {},
                    "must_return": [gap["missing"]],
                })
                # A revision re-runs one agent against the finished pipeline, so
                # it sees every other report — including later stages — but not
                # its own, which it is being asked to replace.
                sends.append(
                    _send(
                        state,
                        original,
                        stage,
                        allowance,
                        upstream_digest(
                            state.get("reports", {}),
                            dispatch,
                            stage + 1,
                            exclude=(gap["agent"],),
                        ),
                        revision_note=gap["missing"],
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
