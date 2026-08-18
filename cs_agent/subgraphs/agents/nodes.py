"""Nodes shared by the five private specialist subgraphs."""

from __future__ import annotations

import json
import operator
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph.message import add_messages

from cs_agent.config.limits import get_limits
from cs_agent.contracts import AgentBrief, REPORT_SCHEMAS, brief_depth
from cs_agent.graph.nodes.record_evidence import _extract
from cs_agent.llm import get_model, schema_instruction, structured
from cs_agent.tool_errors import count_failures, trailing_tool_messages

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
COMMON_PROMPT = (PROMPTS / "agent_common.md").read_text(encoding="utf-8")


DEPTH_NOTE = {
    "overview": (
        "DEPTH: overview. Answer at range level. Name the families with their "
        "published descriptions and SKU counts, and stop there — do not reach "
        "ordering codes, specifications, or prices. Finish by writing the "
        "follow_up_questions that would let the user narrow down next turn. "
        "Spare tool budget is not work still to do."
    ),
    "detailed": (
        "DEPTH: detailed. Take the objective all the way to ordering codes and "
        "the specifications the brief asks for."
    ),
}


class SpecialistState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    # The transcript of this agent's previous attempt, when the gate sent it
    # back. Distinct from `messages`, which the add_messages reducer owns.
    prior_messages: list[AnyMessage]
    question: str
    brief: dict[str, Any]
    upstream: dict[str, dict[str, Any]]
    agent_name: str
    allowance: int
    evidence: Annotated[list[dict[str, Any]], operator.add]
    tool_calls_used: int
    tool_failures: int
    report: dict[str, Any]


def prepare(state: SpecialistState) -> dict[str, Any]:
    brief = AgentBrief.model_validate(state["brief"])
    if resumed := _resume_messages(state, brief):
        # A retry that starts from the transcript keeps everything already
        # retrieved, so its budget covers only what the revision note asks for.
        return {
            "agent_name": brief.agent,
            "allowance": min(brief.allowance, get_limits().revision_tool_budget),
            "tool_calls_used": 0,
            "tool_failures": 0,
            "messages": resumed,
        }
    opening = (
        f"User question: {state.get('question', '')}\n"
        f"Known parameters: {json.dumps(brief.parameters or {}, default=str)}\n"
        f"Your objective: {brief.objective}"
    )
    # Earlier stages arrive as digests rather than as instructions, so they go
    # on the opening turn beside the question the agent is working from.
    if upstream := state.get("upstream"):
        opening += (
            "\n\nAlready established by earlier stages — build on this rather "
            "than retrieving it again:\n"
            + json.dumps(upstream, indent=2, default=str)
        )
    if brief.revision_note:
        opening += f"\n\nRevision requested: {brief.revision_note}"
    return {
        "agent_name": brief.agent,
        "allowance": brief.allowance,
        "tool_calls_used": 0,
        "tool_failures": 0,
        "messages": [HumanMessage(content=opening)],
    }


def _resume_messages(
    state: SpecialistState, brief: AgentBrief
) -> list[AnyMessage] | None:
    """Re-enter a specialist on its own transcript instead of from nothing.

    A gate failure is nearly always about the shape of the report — a missing
    citation, an absent follow-up question — and the retrieval that would answer
    it is already sitting in the transcript. Restarting empty made the specialist
    re-run every tool call to fix a field, which measured at 471s of a 963s run.
    Coming back on the transcript also keeps the server's KV prefix, so the
    retry's first turn costs a few hundred tokens rather than the whole history.
    """
    prior = state.get("prior_messages")
    if not prior or not brief.revision_note:
        return None
    return [
        *_settled(prior),
        HumanMessage(
            content=(
                "Your report was rejected. Fix exactly this and nothing else:\n"
                f"{brief.revision_note}\n\n"
                "Everything above is still yours — do not retrieve it again. "
                "Call a tool only if the fix needs a fact you have not already "
                "got; otherwise answer with no tool call and the report will be "
                "rebuilt from this transcript."
            )
        ),
    ]


def _settled(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Close off a tool call the loop stopped before answering.

    The loop can exit with the model's last request unserved — budget ran out
    mid-turn. Sending that history back with an unanswered tool_call is a
    protocol error at most providers, so the gap is filled with the reason.
    """
    if not messages:
        return []
    last = messages[-1]
    calls = getattr(last, "tool_calls", None)
    if not calls:
        return list(messages)
    return [
        *messages,
        *(
            ToolMessage(
                content="Not executed: the tool budget ran out on this turn.",
                tool_call_id=call["id"],
                name=call.get("name", "unknown"),
            )
            for call in calls
        ),
    ]


def _budget_note(state: SpecialistState) -> str:
    return (
        f"Tool calls used: {state.get('tool_calls_used', 0)}."
        f"\nFailed calls: {state.get('tool_failures', 0)}."
    )


@lru_cache(maxsize=8)
def _role_prompt(agent_name: str) -> str:
    return (PROMPTS / "agents" / f"{agent_name}.md").read_text(encoding="utf-8")


def _system_prompt(agent_name: str, state: SpecialistState) -> str:
    """The specialist's system prompt, identical for the loop and the report.

    Both nodes build it from here so the report call shares a byte-identical
    prefix with the loop turn before it; a single differing character at the
    front would cost a full re-read of the accumulated transcript.
    """
    brief = AgentBrief.model_validate(state["brief"])
    system = COMMON_PROMPT.format(
        brief_json=json.dumps(brief.model_dump(), default=str),
        allowance=state.get("allowance", brief.allowance),
        depth_note=DEPTH_NOTE[brief_depth(state["brief"])],
    )
    return system + "\n\n" + _role_prompt(agent_name)


def make_agent_node(agent_name: str, tools: list[Any]):
    def agent(state: SpecialistState) -> dict[str, Any]:
        system = _system_prompt(agent_name, state)
        # The running counters change every turn, so they go after the history
        # rather than into the system prompt. Anything before the first differing
        # token is a KV cache hit, and a counter at the front of the prompt would
        # force the server to re-read the whole accumulated transcript each turn.
        try:
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
        except Exception as exc:
            # Ollama (and similar) can 500 on a malformed tool-call XML payload.
            # Stop the tool loop so the sibling specialists and composer still run.
            response = AIMessage(
                content=(
                    f"Model call failed ({type(exc).__name__}: {exc}). "
                    "Do not call more tools. Produce the report from evidence "
                    "already gathered."
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


def make_report_node(agent_name: str, tools: list[Any] | None = None):
    schema = REPORT_SCHEMAS[agent_name]

    def report(state: SpecialistState) -> dict[str, Any]:
        # Continue the agent's own conversation rather than restating it as a
        # JSON payload. The old payload carried the transcript *and* an
        # `evidence` re-encoding of the same tool outputs — 407,618 chars on the
        # run that motivated this, 53% of it the duplicate — and, because it
        # opened with a fresh system prompt, none of it hit the server's KV
        # cache: 642 tok/s against the 2,771 tok/s the agent loop was getting on
        # the identical text. Reusing the thread makes the prefix free and hands
        # the model the tool results in their original form.
        instruction = (
            "Produce the specialist report from the work above. Do not call a "
            "tool — the retrieval is finished. Every specification finding must "
            "cite a SourceRef containing its sku_code."
        )
        # The role prompt that explains depth is bound to the agent node, not to
        # this one, so restate the overview contract here. Without it the report
        # comes back with no follow_up_questions, fails the gate, and the retry
        # re-runs the whole specialist — retrieval included.
        if brief_depth(state["brief"]) == "overview":
            instruction += (
                " This brief was answered at overview depth: report the families "
                "and leave representative_skus empty, and populate "
                "follow_up_questions with the two or three questions that would "
                "let the user narrow down on the next turn. A rating span read "
                "off a category or family page describes the range, not one "
                "product, so record it with kind 'catalogue' — 'specification' "
                "is for a value retrieved against a particular sku_code."
            )
        result = structured(
            "agent",
            [
                SystemMessage(content=_system_prompt(agent_name, state)),
                *_settled(state.get("messages", [])),
                # Last, not first: `structured` would otherwise prepend the
                # schema and break the prefix this node exists to reuse.
                HumanMessage(
                    content=f"{instruction}\n\n{schema_instruction(schema)}"
                ),
            ],
            schema,
            # Bound, not offered: the server renders tool schemas into the
            # prompt prefix, so dropping them here would make this a different
            # prefix from the loop's and re-read the transcript from cold.
            tools=tools,
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
