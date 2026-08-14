"""Nodes shared by the five private specialist subgraphs."""

from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph.message import add_messages

from cs_agent.config.limits import get_limits
from cs_agent.contracts import AgentBrief, REPORT_SCHEMAS
from cs_agent.graph.nodes.record_evidence import _extract
from cs_agent.llm import get_model, structured
from cs_agent.tool_errors import count_failures, trailing_tool_messages

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
COMMON_PROMPT = (PROMPTS / "agent_common.md").read_text(encoding="utf-8")


class SpecialistState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    question: str
    brief: dict[str, Any]
    agent_name: str
    allowance: int
    evidence: Annotated[list[dict[str, Any]], operator.add]
    tool_calls_used: int
    tool_failures: int
    report: dict[str, Any]


def prepare(state: SpecialistState) -> dict[str, Any]:
    brief = AgentBrief.model_validate(state["brief"])
    return {
        "agent_name": brief.agent,
        "allowance": brief.allowance,
        "tool_calls_used": 0,
        "tool_failures": 0,
        "messages": [
            HumanMessage(
                content=(
                    f"User question: {state.get('question', '')}\n"
                    f"Your objective: {brief.objective}"
                )
            )
        ],
    }


def _budget_note(state: SpecialistState) -> str:
    return (
        f"Tool calls used: {state.get('tool_calls_used', 0)}."
        f"\nFailed calls: {state.get('tool_failures', 0)}."
    )


def make_agent_node(agent_name: str, tools: list[Any]):
    role_prompt = (PROMPTS / "agents" / f"{agent_name}.md").read_text(encoding="utf-8")

    def agent(state: SpecialistState) -> dict[str, Any]:
        brief = AgentBrief.model_validate(state["brief"])
        system = COMMON_PROMPT.format(
            brief_json=json.dumps(brief.model_dump(), default=str),
            allowance=state.get("allowance", brief.allowance),
        )
        system += "\n\n" + role_prompt
        # The running counters change every turn, so they go after the history
        # rather than into the system prompt. Anything before the first differing
        # token is a KV cache hit, and a counter at the front of the prompt would
        # force the server to re-read the whole accumulated transcript each turn.
        response = (
            get_model("agent")
            .bind_tools(tools)
            .invoke(
                [
                    SystemMessage(content=system),
                    *state.get("messages", []),
                    HumanMessage(content=_budget_note(state)),
                ]
            )
        )
        return {"messages": [response]}

    return agent


def record(state: SpecialistState) -> dict[str, Any]:
    results = trailing_tool_messages(state.get("messages"))
    evidence: list[dict[str, Any]] = []
    for message in results:
        content: Any = message.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        for item in _extract(content, message.name or "unknown"):
            item["agent"] = state["agent_name"]
            evidence.append(item)
    return {
        "evidence": evidence,
        "tool_calls_used": state.get("tool_calls_used", 0) + len(results),
        "tool_failures": state.get("tool_failures", 0) + count_failures(results),
    }


def make_report_node(agent_name: str):
    schema = REPORT_SCHEMAS[agent_name]

    def report(state: SpecialistState) -> dict[str, Any]:
        transcript = []
        for message in state.get("messages", []):
            item = {"type": message.type, "content": message.content}
            if calls := getattr(message, "tool_calls", None):
                item["tool_calls"] = calls
            transcript.append(item)
        payload = {
            "brief": state["brief"],
            "question": state.get("question"),
            "tool_calls_used": state.get("tool_calls_used", 0),
            "evidence": state.get("evidence", []),
            "transcript": transcript,
        }
        result = structured(
            "agent",
            [
                SystemMessage(
                    content=(
                        "Produce the specialist report. Every specification finding "
                        "must cite a SourceRef containing its sku_code."
                    )
                ),
                HumanMessage(content=json.dumps(payload, default=str)),
            ],
            schema,
        )
        result.tool_calls_used = state.get("tool_calls_used", 0)
        return {"report": result.model_dump()}

    return report


def should_use_tools(state: SpecialistState) -> str:
    messages = state.get("messages", [])
    calls = getattr(messages[-1], "tool_calls", []) if messages else []
    remaining = state.get("allowance", 0) - state.get("tool_calls_used", 0)
    failed = state.get("tool_failures", 0) >= get_limits().tool_failure_limit
    return "tools" if calls and len(calls) <= remaining and not failed else "report"


def after_record(state: SpecialistState) -> str:
    if state.get("tool_calls_used", 0) >= state.get("allowance", 0):
        return "report"
    if state.get("tool_failures", 0) >= get_limits().tool_failure_limit:
        return "report"
    return "agent"
