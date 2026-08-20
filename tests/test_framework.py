"""Offline v2 framework tests. No live model, database, or embedding calls."""

from __future__ import annotations

import importlib
import json
import os
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import ValidationError

from cs_agent.backends.fixtures import FixturesBackend
from cs_agent.graph.nodes.gate import _violations
from cs_agent.subgraphs.agents.nodes import _asked_for
from cs_agent.subgraphs.agents.report_modes import (
    backfill_report,
    derive_report,
    needs_model_fallback,
    raw_bundle,
    report_mode,
    resolve_mode,
)
from cs_agent.backends.read_only_sql import read_only_sql_error
from cs_agent.config.limits import clear_limits_cache, get_limits
from cs_agent.contracts import (
    AdvisoryReport,
    AgentBrief,
    ComparisonReport,
    ComparisonTable,
    ComplianceReport,
    DiscoveryReport,
    FamilyBrief,
    Finding,
    Plan,
    SourceRef,
    SpecSelectionReport,
)
from cs_agent.config.contact import clear_contact_cache, get_contact
from cs_agent.embeddings.factory import resolve_embedding
from cs_agent.llm.factory import _keep_alive
from cs_agent.graph.build import (
    _after_composer,
    _after_gate,
    _after_planner,
    _run_specialist,
    build_graph,
    next_stage,
    stages_in,
)
from cs_agent.graph.digest import digest_report, upstream_digest
from cs_agent.llm import streaming
# By module path: `cs_agent.graph.nodes.composer` also names a function
# re-exported from the package, and `out_of_scope` likewise.
composer_module = importlib.import_module("cs_agent.graph.nodes.composer")
out_of_scope_module = importlib.import_module("cs_agent.graph.nodes.out_of_scope")
tool_node_module = importlib.import_module("cs_agent.subgraphs.agents.tool_node")
from cs_agent.graph.nodes.gate import gate
from cs_agent.llm import context_guard
from cs_agent.llm.context_guard import check_request, check_response
from cs_agent.subgraphs.analytics import nodes as analytics_nodes
from cs_agent.graph.state import merge_reports
from cs_agent.llm.factory import clear_model_cache, resolve_endpoint
from cs_agent.observability import (
    AGENT_METADATA_KEY,
    AgentCallbackHandler,
    agent_scoped_config,
    set_active_trace,
)
from cs_agent.run import _initial_state
from cs_agent.subgraphs.agents import build_specialist_graph
from cs_agent.tool_errors import count_failures, trailing_tool_messages
from cs_agent.tools.registry import TOOLS_BY_NAME, tools_for_agent
from cs_agent.tools.schemas import (
    CatalogueMapArgs,
    ListCanonicalSpecsArgs,
    ProductSearchArgs,
    SearchDocumentsArgs,
)

ROOT = Path(__file__).parents[1]


class _StreamingModel:
    """A chat model whose stream yields the pieces it was given."""

    def __init__(
        self, *pieces, metadata=None, tool_call_chunks=None, invoke_result=None
    ):
        self.pieces = pieces
        self.metadata = metadata
        self.tool_call_chunks = tool_call_chunks
        self.invoke_result = invoke_result or AIMessage(content="invoked")
        self.invoked = False

    def stream(self, messages):
        from langchain_core.messages import AIMessageChunk

        if self.tool_call_chunks:
            for chunk in self.tool_call_chunks:
                yield AIMessageChunk(content="", tool_call_chunks=[chunk])
            return
        last = len(self.pieces) - 1
        for index, piece in enumerate(self.pieces):
            yield AIMessageChunk(
                content=piece,
                response_metadata=(self.metadata or {}) if index == last else {},
            )

    def invoke(self, messages):
        self.invoked = True
        return self.invoke_result


@contextmanager
def _screen():
    """Run with a trace that captures, rather than prints, streamed lines."""
    class _Lines(list):
        """Captured screen writes, with the trace's events alongside them."""

        events: list

    lines = _Lines()

    def write(text: str, *, end: str = "\n") -> None:
        lines.append(text)

    events: list[tuple[str, dict]] = []
    lines.events = events
    trace = SimpleNamespace(
        print_to_screen=True,
        listener=None,
        write=write,
        event=lambda name, **details: events.append((name, details)),
        # Listener-only records — streamed answer fragments — land in the same
        # list, told apart by their event name.
        notify=lambda name, **details: events.append((name, details)),
        events=events,
    )
    set_active_trace(trace)
    try:
        yield lines
    finally:
        set_active_trace(None)


class LimitsAndModelTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("CS_GLOBAL_TOOL_BUDGET", None)
        os.environ.pop("CS_MODELS", None)
        clear_limits_cache()
        clear_model_cache()

    def test_limits_load_and_override(self) -> None:
        self.assertEqual(100, get_limits().global_tool_budget)
        os.environ["CS_GLOBAL_TOOL_BUDGET"] = "55"
        clear_limits_cache()
        self.assertEqual(55, get_limits().global_tool_budget)

    def test_shared_agent_and_intake_endpoint_routing(self) -> None:
        self.assertEqual(resolve_endpoint("agent"), resolve_endpoint("intake"))
        os.environ["CS_MODELS"] = "agent:qwen_a3b"
        self.assertEqual("Qwen/Qwen3.6-35B-A3B", resolve_endpoint("agent").model)

    def test_gte_profile_is_active_without_loading_model(self) -> None:
        profile = resolve_embedding()
        self.assertEqual("Alibaba-NLP/gte-base-en-v1.5", profile.model)
        self.assertEqual(768, profile.dimension)
        self.assertTrue(profile.normalize)


class ContractAndGateTests(unittest.TestCase):
    def base(self, agent: str) -> dict:
        return {
            "agent": agent,
            "status": "complete",
            "summary": "fixture",
            "findings": [],
            "sources": [],
            "gaps": [],
            "tool_calls_used": 2,
            "caveats": [],
        }

    def test_report_schemas_cover_all_roles(self) -> None:
        DiscoveryReport(
            **self.base("discovery"),
            families=[FamilyBrief(name="MCCB")],
            representative_skus=["WIN2-125-3P-63"],
        )
        SpecSelectionReport(
            **self.base("spec_selection"),
            candidates=[],
            no_candidates_reason="No 100 kA fixture",
            filters_tried=["icu_ka gte 100"],
        )
        ComparisonReport(
            **self.base("comparison"),
            table=ComparisonTable(
                axes=["rated_current_a"],
                rows={"A": {}, "B": {}},
            ),
        )
        ComplianceReport(
            **self.base("compliance"),
            not_established=["certificate"],
        )
        AdvisoryReport(
            **{**self.base("solution_advisory"), "gaps": ["No application data"]},
            engineering_guidance=[],
            catalog_backed=[],
        )

    def test_gate_rejects_taxonomy_only_discovery(self) -> None:
        report = DiscoveryReport(
            **self.base("discovery"),
            families=[FamilyBrief(name="MCCB")],
        )
        result = gate(
            {
                "dispatch": [{"agent": "discovery", "stage": 1}],
                "reports": {"discovery": report.model_dump()},
                "stage_index": 1,
                "gate_retries": {},
            }
        )
        self.assertFalse(result["gate_result"]["ok"])
        self.assertEqual({"1": 1}, result["gate_retries"])

    def test_gate_ignores_stages_that_have_not_run_yet(self) -> None:
        report = DiscoveryReport(
            **self.base("discovery"),
            families=[FamilyBrief(name="MCCB")],
            representative_skus=["SKU-1"],
        )
        result = gate(
            {
                "dispatch": [
                    {"agent": "discovery", "stage": 1, "depth": "detailed"},
                    {"agent": "spec_selection", "stage": 2},
                ],
                "reports": {"discovery": report.model_dump()},
                "stage_index": 1,
                "gate_retries": {},
            }
        )
        self.assertTrue(result["gate_result"]["ok"])
        self.assertNotIn("gate_retries", result)

    def test_gate_requires_sku_source_for_specification(self) -> None:
        report = ComplianceReport(
            **{
                **self.base("compliance"),
                "findings": [
                    Finding(
                        statement="IEC claim",
                        kind="specification",
                        source=SourceRef(source_of_truth="brochure"),
                    )
                ],
            },
            standards=[],
            not_established=["test"],
        )
        result = gate(
            {
                "dispatch": [{"agent": "compliance", "stage": 1}],
                "reports": {"compliance": report.model_dump()},
                "stage_index": 1,
                "gate_retries": {},
            }
        )
        self.assertFalse(result["gate_result"]["ok"])

    def test_report_reducer_is_parallel_safe_and_resettable(self) -> None:
        merged = merge_reports({"discovery": {"status": "complete"}}, {
            "comparison": {"status": "partial"}
        })
        self.assertEqual({"discovery", "comparison"}, set(merged))
        self.assertEqual({}, merge_reports(merged, {"__reset__": {}}))


class AnswerDepthTests(unittest.TestCase):
    """Breadth is planned, not emergent.

    A broad question like "what air circuit breakers do you have" is answered by
    naming the ranges and asking what the user is after. Before depth existed the
    gate demanded ordering codes and the full tool budget invited a sweep for
    them, so discovery spent 19 calls elaborating an answer that one taxonomy
    browse already held.
    """

    def _brief(self, agent: str = "discovery", **kwargs: Any) -> dict[str, Any]:
        return AgentBrief(agent=agent, objective="o", **kwargs).model_dump()

    def test_discovery_defaults_to_overview_and_others_to_detailed(self) -> None:
        plan = Plan(
            intent="x",
            dispatch=[
                AgentBrief(agent="discovery", objective="map"),
                AgentBrief(agent="spec_selection", objective="shortlist"),
            ],
        )
        depths = {brief.agent: brief.depth for brief in plan.dispatch}
        self.assertEqual(
            {"discovery": "overview", "spec_selection": "detailed"}, depths
        )

    def test_the_planner_can_override_the_default(self) -> None:
        plan = Plan(
            intent="x",
            dispatch=[
                AgentBrief(agent="discovery", objective="map", depth="detailed")
            ],
        )
        self.assertEqual("detailed", plan.dispatch[0].depth)

    def test_an_overview_brief_is_capped_to_the_overview_budget(self) -> None:
        state = {
            "plan": {"needs_clarification": False},
            "dispatch": [self._brief()],
            "standalone_question": "what ACBs do you have",
            "tool_calls_made": 0,
            "turn_tool_calls_start": 0,
        }
        sends = _after_planner(state)
        limits = get_limits()
        self.assertEqual(
            limits.overview_tool_budget, sends[0].arg["brief"]["allowance"]
        )
        self.assertLess(limits.overview_tool_budget, limits.per_agent_tool_budget)

    def test_an_overview_passes_the_gate_without_ordering_codes(self) -> None:
        report = DiscoveryReport(
            agent="discovery",
            status="complete",
            summary="Three ACB ranges",
            families=[FamilyBrief(name="ACB – WiNmaster 3", sku_count=157)],
            follow_up_questions=["What rated current do you need?"],
        )
        result = gate(
            {
                "dispatch": [self._brief(stage=1)],
                "reports": {"discovery": report.model_dump()},
                "stage_index": 1,
                "gate_retries": {},
            }
        )
        self.assertTrue(result["gate_result"]["ok"])

    def test_an_overview_without_a_follow_up_question_fails_the_gate(self) -> None:
        report = DiscoveryReport(
            agent="discovery",
            status="complete",
            summary="Three ACB ranges",
            families=[FamilyBrief(name="ACB – WiNmaster 3", sku_count=157)],
        )
        result = gate(
            {
                "dispatch": [self._brief(stage=1)],
                "reports": {"discovery": report.model_dump()},
                "stage_index": 1,
                "gate_retries": {},
            }
        )
        self.assertFalse(result["gate_result"]["ok"])

    def test_a_detailed_discovery_still_owes_ordering_codes(self) -> None:
        report = DiscoveryReport(
            agent="discovery",
            status="complete",
            summary="Three ACB ranges",
            families=[FamilyBrief(name="ACB – WiNmaster 3", sku_count=157)],
            follow_up_questions=["What rated current do you need?"],
        )
        result = gate(
            {
                "dispatch": [self._brief(stage=1, depth="detailed")],
                "reports": {"discovery": report.model_dump()},
                "stage_index": 1,
                "gate_retries": {},
            }
        )
        self.assertFalse(result["gate_result"]["ok"])

    def test_an_overview_may_state_a_span_without_a_sku_to_cite(self) -> None:
        """The SKU-source rule is unsatisfiable at a depth that reaches no SKU.

        "Up to 6300 A in 3 or 4 pole" is published on the Air Circuit Breakers
        category page, not against an ordering code. Enforcing the sku_code rule
        against it failed the gate on every overview that quoted a rating, and
        the retry re-ran the whole specialist.
        """
        report = DiscoveryReport(
            agent="discovery",
            status="complete",
            summary="Three ACB ranges",
            families=[FamilyBrief(name="ACB – AH-AHA", sku_count=316)],
            follow_up_questions=["Which range are you interested in?"],
            findings=[
                Finding(
                    statement="ACBs are rated up to 6300 A in 3 or 4 pole.",
                    kind="specification",
                )
            ],
        )
        result = gate(
            {
                "dispatch": [self._brief(stage=1)],
                "reports": {"discovery": report.model_dump()},
                "stage_index": 1,
                "gate_retries": {},
            }
        )
        self.assertTrue(result["gate_result"]["ok"])

    def test_a_detailed_report_still_needs_a_sku_behind_a_specification(self) -> None:
        report = DiscoveryReport(
            agent="discovery",
            status="complete",
            summary="Three ACB ranges",
            families=[FamilyBrief(name="ACB – AH-AHA", sku_count=316)],
            representative_skus=["AH40D4CSMP3.1MF(S)"],
            findings=[
                Finding(statement="Rated to 6300 A.", kind="specification"),
                Finding(statement="Rated to 4000 A.", kind="specification"),
            ],
        )
        result = gate(
            {
                "dispatch": [self._brief(stage=1, depth="detailed")],
                "reports": {"discovery": report.model_dump()},
                "stage_index": 1,
                "gate_retries": {},
            }
        )
        violations = result["gate_result"]["failures"][0]["violations"]
        self.assertIn("sku_code", " ".join(violations))
        # Two offending findings, one sentence: the violations become the
        # specialist's revision note, and repetition reads as extra faults.
        self.assertEqual(len(violations), len(set(violations)))

    def test_the_report_node_is_told_to_write_follow_up_questions(self) -> None:
        """The gate check is only cheap if the report reliably carries the field.

        The role prompt explaining depth is bound to the agent node, so the
        report node needs the overview contract restated. Without it the report
        came back with no follow_up_questions, failed the gate, and the retry
        re-ran the specialist from scratch — 5 more tool calls re-walking a
        taxonomy it had already walked.
        """
        from cs_agent.subgraphs.agents.nodes import make_report_node

        seen: dict[str, Any] = {}

        def _structured(node, messages, schema, **kw):
            # The report node continues the agent's thread, so its instruction
            # is the trailing message, not the system prompt.
            seen[node] = messages[-1].content
            return schema(agent="discovery", status="complete", summary="s")

        node = make_report_node("discovery")
        # Pinned: the default `auto` mode skips the model entirely on an
        # overview brief, so the instruction under test is never built.
        with patch.dict(os.environ, {"CS_REPORT_MODE": "llm"}), patch(
            "cs_agent.subgraphs.agents.nodes.structured", side_effect=_structured
        ):
            node({"brief": self._brief(), "agent_name": "discovery", "messages": []})
        self.assertIn("follow_up_questions", seen["agent"])

    def test_the_report_node_stays_quiet_about_depth_when_detailed(self) -> None:
        from cs_agent.subgraphs.agents.nodes import make_report_node

        seen: dict[str, Any] = {}

        def _structured(node, messages, schema, **kw):
            seen[node] = messages[-1].content
            return schema(agent="discovery", status="complete", summary="s")

        node = make_report_node("discovery")
        with patch(
            "cs_agent.subgraphs.agents.nodes.structured", side_effect=_structured
        ):
            node(
                {
                    "brief": self._brief(depth="detailed"),
                    "agent_name": "discovery",
                    "messages": [],
                }
            )
        # The schema rides on the same message, and DiscoveryReport declares the
        # field, so look for the sentence the overview branch adds.
        self.assertNotIn("populate", seen["agent"])

    def test_the_specialist_prompt_states_the_depth_it_is_working_at(self) -> None:
        from cs_agent.subgraphs.agents.nodes import DEPTH_NOTE, make_agent_node

        captured: dict[str, Any] = {}

        class _Model:
            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                captured["system"] = messages[0].content
                return HumanMessage(content="")

        node = make_agent_node("discovery", [])
        with patch("cs_agent.subgraphs.agents.nodes.get_model", return_value=_Model()):
            node({"brief": self._brief(), "allowance": 5, "messages": []})
        self.assertIn(DEPTH_NOTE["overview"], captured["system"])
        self.assertNotIn(DEPTH_NOTE["detailed"], captured["system"])


class LatencyShapeTests(unittest.TestCase):
    """Each of these pins a change made because a run was measured too slow.

    The profile of the run that prompted them: 95–99% of wall time was model
    inference, tools were 0.9%, and the single largest stage was the specialist
    report at 48% of all model time.
    """

    @staticmethod
    def _brief(**kw: Any) -> dict[str, Any]:
        return AgentBrief(
            agent="discovery",
            objective="map ACBs",
            depth="detailed",
            allowance=20,
            **kw,
        ).model_dump()

    def _capture_report_messages(self, state: dict[str, Any]) -> list[Any]:
        from cs_agent.subgraphs.agents.nodes import make_report_node

        seen: dict[str, list[Any]] = {}

        def _structured(node, messages, schema, **kw):
            seen["messages"] = messages
            return schema(agent="discovery", status="complete", summary="s")

        node = make_report_node("discovery")
        with patch(
            "cs_agent.subgraphs.agents.nodes.structured", side_effect=_structured
        ):
            node(state)
        return seen["messages"]

    def test_the_report_continues_the_agent_thread(self) -> None:
        """The prefix has to match the loop's, or the server re-reads it all.

        The old node built a fresh system prompt and one JSON payload, which
        shared nothing with the conversation that had just run: 642 tok/s of
        prefill against the 2,771 tok/s the loop was getting on the same text.
        """
        from cs_agent.subgraphs.agents.nodes import _system_prompt, make_agent_node

        history = [
            HumanMessage(content="User question: what ACBs are there?"),
            AIMessage(content="looked it up"),
        ]
        state = {
            "brief": self._brief(),
            "agent_name": "discovery",
            "allowance": 20,
            "messages": history,
        }
        messages = self._capture_report_messages(state)
        self.assertEqual(history, list(messages[1:-1]))

        captured: dict[str, Any] = {}

        class _Model:
            def bind_tools(self, tools):
                return self

            def invoke(self, msgs):
                captured["system"] = msgs[0].content
                return AIMessage(content="")

        with patch("cs_agent.subgraphs.agents.nodes.get_model", return_value=_Model()):
            make_agent_node("discovery", [])(state)
        # Byte-identical, not merely similar: one differing character at the
        # front costs a full re-read of the accumulated transcript.
        self.assertEqual(captured["system"], messages[0].content)
        self.assertEqual(_system_prompt("discovery", state), messages[0].content)

    def test_the_report_no_longer_restates_the_transcript_as_evidence(self) -> None:
        """Transcript plus evidence was the same tool output twice.

        On the measured run that payload was 407,618 chars, 214,427 of it the
        `evidence` re-encoding.
        """
        state = {
            "brief": self._brief(),
            "agent_name": "discovery",
            "allowance": 20,
            "messages": [HumanMessage(content="q")],
            "evidence": [
                {"tool": "taxonomy_browse", "text": "UNIQUE-EVIDENCE-MARKER"}
            ],
        }
        rendered = json.dumps(
            [m.content for m in self._capture_report_messages(state)], default=str
        )
        self.assertNotIn("UNIQUE-EVIDENCE-MARKER", rendered)

    def test_the_schema_rides_last_so_it_cannot_break_the_prefix(self) -> None:
        messages = self._capture_report_messages(
            {
                "brief": self._brief(),
                "agent_name": "discovery",
                "allowance": 20,
                "messages": [HumanMessage(content="q")],
            }
        )
        self.assertIn("JSON Schema", messages[-1].content)
        self.assertNotIn("JSON Schema", messages[0].content)

    def test_an_unanswered_tool_call_is_closed_before_the_thread_is_reused(
        self,
    ) -> None:
        """The loop can stop mid-turn; providers reject a dangling call."""
        pending = AIMessage(
            content="",
            tool_calls=[{"name": "get_sku", "args": {"sku_code": "X"}, "id": "c1"}],
        )
        messages = self._capture_report_messages(
            {
                "brief": self._brief(),
                "agent_name": "discovery",
                "allowance": 20,
                "messages": [HumanMessage(content="q"), pending],
            }
        )
        answered = [m for m in messages if isinstance(m, ToolMessage)]
        self.assertEqual(["c1"], [m.tool_call_id for m in answered])

    def test_the_loop_is_told_not_to_write_the_report_itself(self) -> None:
        """It wrote the report twice: once as prose, then again as JSON.

        Measured at 4,423 characters of discarded prose on the turn before the
        report node ran — about 100s of decode on a model at 11 tok/s.
        """
        from cs_agent.subgraphs.agents.nodes import COMMON_PROMPT

        self.assertIn("You do not write the report", COMMON_PROMPT)
        self.assertIn("call no tool", COMMON_PROMPT)

    def test_the_report_keeps_the_loop_tools_bound(self) -> None:
        """A server renders tool schemas into the prompt prefix.

        Measured directly against Ollama: identical messages prefill at 91,611
        tok/s with tools bound and repeated, and at 808 tok/s — cold — with the
        tools removed. Dropping them here re-reads the whole transcript.
        """
        from cs_agent.subgraphs.agents.nodes import make_report_node

        seen: dict[str, Any] = {}

        def _structured(node, messages, schema, **kw):
            seen.update(kw)
            return schema(agent="discovery", status="complete", summary="s")

        tools = tools_for_agent("discovery")
        node = make_report_node("discovery", tools)
        with patch(
            "cs_agent.subgraphs.agents.nodes.structured", side_effect=_structured
        ):
            node(
                {
                    "brief": self._brief(),
                    "agent_name": "discovery",
                    "allowance": 20,
                    "messages": [HumanMessage(content="q")],
                }
            )
        self.assertEqual(tools, seen["tools"])
        # Bound so the prefix matches, never so a tool gets called.
        messages = self._capture_report_messages(
            {
                "brief": self._brief(),
                "agent_name": "discovery",
                "allowance": 20,
                "messages": [HumanMessage(content="q")],
            }
        )
        self.assertIn("Do not call a tool", messages[-1].content)

    def test_structured_binds_tools_only_when_asked(self) -> None:
        # By module path: `cs_agent.llm.structured` also names the function.
        structured_module = importlib.import_module("cs_agent.llm.structured")

        bound: dict[str, Any] = {}

        class _Model:
            def bind_tools(self, tools):
                bound["tools"] = tools
                return self

            def invoke(self, messages):
                return AIMessage(content='{"name": "ACB"}')

        with patch.object(structured_module, "get_model", return_value=_Model()):
            structured_module.structured(
                "planner", [HumanMessage(content="q")], FamilyBrief
            )
            self.assertNotIn("tools", bound)
            structured_module.structured(
                "planner", [HumanMessage(content="q")], FamilyBrief, tools=["t"]
            )
        self.assertEqual(["t"], bound["tools"])

    def test_a_gate_retry_resumes_on_the_transcript(self) -> None:
        """One gate failure cost 471s of a 963s run by restarting empty."""
        from cs_agent.subgraphs.agents.nodes import prepare

        prior = [
            HumanMessage(content="User question: what ACBs are there?"),
            AIMessage(content="three families"),
        ]
        update = prepare(
            {
                "brief": self._brief(revision_note="Cite a sku_code."),
                "prior_messages": prior,
                "question": "what ACBs are there?",
            }
        )
        self.assertEqual(prior, update["messages"][:-1])
        self.assertIn("Cite a sku_code.", update["messages"][-1].content)
        # The retrieval is already done, so the retry gets the small budget.
        self.assertEqual(get_limits().revision_tool_budget, update["allowance"])

    def test_a_first_dispatch_still_starts_from_the_brief(self) -> None:
        from cs_agent.subgraphs.agents.nodes import prepare

        update = prepare({"brief": self._brief(), "question": "what ACBs?"})
        self.assertEqual(1, len(update["messages"]))
        self.assertIn("Your objective", update["messages"][0].content)
        self.assertEqual(20, update["allowance"])

    def test_the_retry_send_carries_the_previous_transcript(self) -> None:
        from cs_agent.graph.build import _send

        prior = [HumanMessage(content="earlier work")]
        send = _send(
            {"transcripts": {"discovery": prior}},
            self._brief(),
            1,
            20,
            {},
            revision_note="fix it",
            resume=True,
        )
        self.assertEqual(prior, send.arg["prior_messages"])
        fresh = _send({}, self._brief(), 1, 20, {})
        self.assertNotIn("prior_messages", fresh.arg)

    def test_a_passing_gate_drops_the_transcripts_it_was_holding(self) -> None:
        """They exist only for a retry; kept, they ride every later checkpoint."""
        report = DiscoveryReport(
            agent="discovery",
            status="complete",
            summary="s",
            families=[FamilyBrief(name="ACB")],
            representative_skus=["SKU-1"],
        ).model_dump()
        passed = gate(
            {
                "dispatch": [{"agent": "discovery", "stage": 1, "depth": "detailed"}],
                "reports": {"discovery": report},
                "transcripts": {"discovery": [HumanMessage(content="work")]},
                "stage_index": 1,
                "gate_retries": {},
            }
        )
        self.assertEqual({"__reset__": []}, passed["transcripts"])
        failed = gate(
            {
                "dispatch": [{"agent": "discovery", "stage": 1, "depth": "detailed"}],
                "reports": {"discovery": {**report, "families": []}},
                "transcripts": {"discovery": [HumanMessage(content="work")]},
                "stage_index": 1,
                "gate_retries": {},
            }
        )
        # A failing stage keeps them: the retry is about to resume on them.
        self.assertNotIn("transcripts", failed)

    def test_an_identical_repeat_call_never_reaches_the_backend(self) -> None:
        """Four identical dead-end calls out of twenty, on the measured run."""
        from cs_agent.subgraphs.agents.tool_node import make_tool_node

        ran: list[dict[str, Any]] = []

        def _fake(state, config=None):
            ran.append(state)
            return {"messages": [ToolMessage(content="{}", tool_call_id="c2")]}

        call = {"name": "list_canonical_specs", "args": {"family": "X"}, "id": "c1"}
        again = {**call, "id": "c2"}
        bound = [SimpleNamespace(name="list_canonical_specs")]
        with patch(
            "cs_agent.subgraphs.agents.tool_node.ToolNode",
            return_value=SimpleNamespace(invoke=_fake),
        ):
            node = make_tool_node(bound)
            result = node(
                {
                    "messages": [
                        AIMessage(content="", tool_calls=[call]),
                        ToolMessage(content="[]", tool_call_id="c1"),
                        AIMessage(content="", tool_calls=[again]),
                    ]
                }
            )
        self.assertEqual([], ran)
        self.assertIn("repeat_of_call", result["messages"][0].content)

    def test_a_fresh_call_alongside_a_repeat_still_runs(self) -> None:
        from cs_agent.subgraphs.agents.tool_node import make_tool_node

        sent: list[Any] = []

        def _fake(state, config=None):
            sent.extend(state["messages"][-1].tool_calls)
            return {"messages": [ToolMessage(content="{}", tool_call_id="c3")]}

        repeat = {"name": "get_sku", "args": {"sku_code": "A"}, "id": "c1"}
        with patch(
            "cs_agent.subgraphs.agents.tool_node.ToolNode",
            return_value=SimpleNamespace(invoke=_fake),
        ):
            result = make_tool_node([SimpleNamespace(name="get_sku")])(
                {
                    "messages": [
                        AIMessage(content="", tool_calls=[repeat]),
                        ToolMessage(content="{}", tool_call_id="c1"),
                        AIMessage(
                            content="",
                            tool_calls=[
                                {**repeat, "id": "c2"},
                                {
                                    "name": "get_sku",
                                    "args": {"sku_code": "B"},
                                    "id": "c3",
                                },
                            ],
                        ),
                    ]
                }
            )
        self.assertEqual(["c3"], [call["id"] for call in sent])
        # Every call the model made gets an answer, or the thread is invalid.
        self.assertEqual({"c2", "c3"}, {m.tool_call_id for m in result["messages"]})

    def test_a_family_that_does_not_exist_says_so(self) -> None:
        """An empty list reads as 'no specs here' and invites the same call."""
        from cs_agent.tools import impl

        with patch.object(impl, "backend", return_value=FixturesBackend()):
            impl._known_families.cache_clear()
            result = impl.list_canonical_specs(family="Switch Sockets")
        self.assertIsInstance(result, dict)
        self.assertEqual("Switch Sockets", result["family_not_found"])
        self.assertEqual(["Switch Sockets"], result["families_not_found"])
        self.assertIn("taxonomy_browse", result["hint"])

    def test_a_family_that_exists_returns_an_envelope(self) -> None:
        from cs_agent.tools import impl

        with patch.object(impl, "backend", return_value=FixturesBackend()):
            impl._known_families.cache_clear()
            family = impl._known_families()[0]
            result = impl.list_canonical_specs(family=family)
        self.assertIsInstance(result, dict)
        self.assertIn("specs", result)
        self.assertNotIn("by_spec_id", result)
        # One family in scope, so every spec it publishes is trivially shared.
        self.assertEqual([family], result["scope"]["groups"])
        self.assertTrue(
            all(family in row["by_group"] for row in result["specs"])
        )

    def test_the_final_answer_streams(self) -> None:
        """~35s of silence at the end of every run, at 12 tok/s."""
        with _screen() as shown, patch.object(
            streaming, "get_model", return_value=_StreamingModel("Three ", "ACB ")
        ):
            text, streamed = streaming.stream_answer("composer", [])
        self.assertEqual("Three ACB ", text)
        self.assertTrue(streamed)
        self.assertIn("Answer", "\n".join(shown))

    def test_nothing_streams_when_nobody_is_watching(self) -> None:
        """Streaming is a display concern; the result must not depend on it."""
        model = _StreamingModel("Three ", "ACB ")
        # No active trace, so `generate` must fall through to plain invoke.
        with patch.object(streaming, "get_model", return_value=model):
            text, streamed = streaming.stream_answer("composer", [])
        self.assertEqual("invoked", text)
        self.assertFalse(streamed)

    def test_a_specialist_stream_is_labelled_and_line_buffered(self) -> None:
        """Five specialists fan out at once; unlabelled tokens would interleave."""
        model = _StreamingModel('{"agent":', ' "discovery",\n', '"status": "ok"}')
        with _screen() as shown:
            message, streamed = streaming.generate(model, [], label="discovery report")
        self.assertTrue(streamed)
        self.assertEqual('{"agent": "discovery",\n"status": "ok"}', message.content)
        self.assertTrue(all(line.startswith("  ┊ [discovery report]") for line in shown))
        # Split on the newline the model emitted, not mid-token.
        self.assertIn('  ┊ [discovery report] {"agent": "discovery",', shown)

    def test_a_long_run_of_output_breaks_on_a_word(self) -> None:
        """Labelled output repeats a prefix, so it cannot let the terminal wrap."""
        model = _StreamingModel("word " * 60)
        with _screen() as shown:
            streaming.generate(model, [], label="discovery")
        body = [line.split("] ", 1)[1] for line in shown if "⏹" not in line]
        self.assertGreater(len(body), 1)
        for line in body:
            self.assertLessEqual(len(line), 100)
        self.assertTrue(all(part == "word" for line in body for part in line.split()))

    def test_parallel_specialists_never_share_a_line(self) -> None:
        """Up to five specialists stream at once into one terminal."""
        import threading

        with _screen() as shown:
            threads = [
                threading.Thread(
                    target=streaming.generate,
                    args=(_StreamingModel(*([f"{name} "] * 40)), []),
                    kwargs={"label": name},
                )
                for name in ("discovery", "compliance", "comparison")
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        for line in shown:
            label = line.split("] ", 1)[0].removeprefix("  ┊ [")
            words = {word for word in line.split("] ", 1)[1].split() if word.isalpha()}
            self.assertLessEqual(words, {label}, f"mixed line: {line!r}")

    def test_a_specialist_stream_reports_what_it_cost(self) -> None:
        """The point of watching is finding output tokens worth cutting."""
        model = _StreamingModel(
            "text",
            metadata={"eval_count": 4481, "eval_duration": 132_000_000_000},
        )
        with _screen() as shown:
            streaming.generate(model, [], label="discovery report")
        self.assertIn("4,481 output tokens in 132.0s (34 tok/s)", "\n".join(shown))

    def test_specialist_streaming_can_be_silenced(self) -> None:
        model = _StreamingModel("text")
        with patch.dict(os.environ, {"CS_STREAM_AGENTS": "false"}), _screen() as shown:
            _, streamed = streaming.generate(model, [], label="discovery")
        self.assertFalse(streamed)
        self.assertEqual([], shown)

    def test_a_streamed_tool_call_survives_reassembly(self) -> None:
        """The loop streams too, and its whole purpose is the tool call."""
        model = _StreamingModel(
            tool_call_chunks=[
                {"name": "taxonomy_browse", "args": "", "id": "1", "index": 0},
                {"name": None, "args": '{"path": []}', "id": None, "index": 0},
            ]
        )
        with _screen():
            message, _ = streaming.generate(model, [], label="discovery")
        self.assertEqual(["taxonomy_browse"], [c["name"] for c in message.tool_calls])
        self.assertEqual({"path": []}, message.tool_calls[0]["args"])


class StagedPlanTests(unittest.TestCase):
    """The planner orders agents; the runtime must be able to trust that order."""

    def _plan(self, *briefs: AgentBrief) -> Plan:
        return Plan(intent="x", dispatch=list(briefs))

    def test_sparse_stage_numbers_are_renumbered_contiguously(self) -> None:
        plan = self._plan(
            AgentBrief(agent="discovery", objective="map", stage=1),
            AgentBrief(agent="spec_selection", objective="shortlist", stage=7),
        )
        self.assertEqual([1, 2], [brief.stage for brief in plan.dispatch])

    def test_a_repeated_agent_keeps_only_its_earliest_stage(self) -> None:
        plan = self._plan(
            AgentBrief(agent="discovery", objective="map", stage=2),
            AgentBrief(agent="discovery", objective="map again", stage=1),
        )
        self.assertEqual(1, len(plan.dispatch))
        self.assertEqual("map again", plan.dispatch[0].objective)

    def test_agents_sharing_a_stage_stay_parallel(self) -> None:
        plan = self._plan(
            AgentBrief(agent="discovery", objective="map", stage=1),
            AgentBrief(agent="compliance", objective="standards", stage=1),
        )
        dispatch = [brief.model_dump() for brief in plan.dispatch]
        self.assertEqual([1], stages_in(dispatch))
        self.assertIsNone(next_stage(dispatch, 1))

    def test_planner_clamps_stages_to_the_configured_maximum(self) -> None:
        module = importlib.import_module("cs_agent.graph.nodes.planner")
        plan = self._plan(
            AgentBrief(agent="discovery", objective="a", stage=1),
            AgentBrief(agent="spec_selection", objective="b", stage=2),
            AgentBrief(agent="comparison", objective="c", stage=3),
            AgentBrief(agent="compliance", objective="d", stage=4),
        )
        with patch.object(module, "structured", return_value=plan):
            result = module.planner(
                {"standalone_question": "q", "session": {}, "assumptions": []}
            )
        stages = [brief["stage"] for brief in result["dispatch"]]
        self.assertLessEqual(max(stages), get_limits().max_stages)
        self.assertEqual(4, len(stages))

    def test_digest_keeps_identifiers_and_drops_the_bulk(self) -> None:
        report = DiscoveryReport(
            agent="discovery",
            status="complete",
            summary="Wintrip covers 16-630 A",
            families=[FamilyBrief(name="MCCB – Wintrip", sku_count=42, url="u")],
            representative_skus=["WT-100"],
            sources=[SourceRef(sku_code="WT-100", brochure_md="b.md")],
            findings=[Finding(statement="noise")],
        ).model_dump()
        digest = digest_report(report)
        self.assertEqual(["WT-100"], digest["representative_skus"])
        self.assertEqual("MCCB – Wintrip", digest["families"][0]["name"])
        self.assertNotIn("findings", digest)
        self.assertNotIn("sources", digest)

    def test_upstream_digest_covers_only_earlier_stages(self) -> None:
        dispatch = [
            AgentBrief(agent="discovery", objective="a", stage=1).model_dump(),
            AgentBrief(agent="spec_selection", objective="b", stage=2).model_dump(),
        ]
        reports = {
            "discovery": {"status": "complete", "summary": "d"},
            "spec_selection": {"status": "complete", "summary": "s"},
        }
        self.assertEqual(
            ["discovery"], list(upstream_digest(reports, dispatch, 2))
        )
        self.assertEqual({}, upstream_digest(reports, dispatch, 1))


class ContextGuardTests(unittest.TestCase):
    """Ollama truncates an oversized prompt silently; that must be visible."""

    def setUp(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        recorder = SimpleNamespace(
            event=lambda name, **details: self.events.append((name, details))
        )
        patcher = patch.object(context_guard, "active_trace", return_value=recorder)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _params(prompt_chars: int, num_ctx: int = 80000, num_predict: int = 20000):
        return {
            "model": "qwen3.6:27b",
            "messages": [{"role": "system", "content": "x" * prompt_chars}],
            "tools": [],
            "options": {"num_ctx": num_ctx, "num_predict": num_predict},
        }

    def test_a_comfortable_prompt_is_silent(self) -> None:
        self.assertIsNone(check_request("agent", self._params(10_000)))
        self.assertEqual([], self.events)

    def test_an_oversized_prompt_reports_the_overflow(self) -> None:
        # 300k chars / 3.5 ≈ 85k tokens against 60k usable (80k − 20k reserved).
        report = check_request("agent", self._params(300_000))
        self.assertEqual("llm.context_overflow", self.events[0][0])
        self.assertGreater(report["overflow_tokens"], 0)
        self.assertEqual(60_000, report["usable_prompt_tokens"])

    def test_a_near_full_prompt_warns_before_it_overflows(self) -> None:
        check_request("agent", self._params(190_000))
        self.assertEqual("llm.context_pressure", self.events[0][0])

    def test_tool_schemas_count_toward_the_window(self) -> None:
        params = self._params(1_000)
        # Schemas alone: 100 × 2,000 chars ≈ 57k tokens against 60k usable, with
        # only 1,000 chars of messages. Counting messages only would miss it.
        params["tools"] = [
            {"name": f"t{i}", "description": "d" * 2_000} for i in range(100)
        ]
        report = check_request("agent", params)
        self.assertIsNotNone(report)
        self.assertGreater(report["estimated_tool_schema_tokens"], 50_000)
        self.assertLess(report["estimated_message_tokens"], 1_000)

    def test_an_endpoint_without_num_ctx_is_not_policed(self) -> None:
        params = self._params(500_000)
        params["options"] = {}
        self.assertIsNone(check_request("agent", params))
        self.assertEqual([], self.events)

    def test_a_full_window_of_evaluated_tokens_confirms_truncation(self) -> None:
        check_response("agent", self._params(10), {"prompt_eval_count": 80_000})
        self.assertEqual("llm.prompt_truncated", self.events[0][0])

    def test_a_cache_shortened_prompt_count_is_not_reported(self) -> None:
        """Prefix-cache hits are not re-evaluated, so a low count proves nothing."""
        check_response("agent", self._params(10), {"prompt_eval_count": 1_200})
        self.assertEqual([], self.events)


class AnalyticsRegistryTests(unittest.TestCase):
    """The spec registry used to inject ~108k tokens into every analytics call."""

    @staticmethod
    def _rows(count: int, *, canonical_from: int = 10_000) -> list[dict[str, Any]]:
        return [
            {
                "family": f"fam{index % 7}",
                "spec_id": f"spec_{index}",
                "spec_label": f"Spec {index}",
                "unit": "A",
                "value_kind": "scalar",
                "is_canonical_spec": int(index >= canonical_from),
                "sku_count": index,
                "composite_count": 0,
                "observed_min": 1,
                "observed_max": 2,
            }
            for index in range(count)
        ]

    def _prepare(self, rows, state):
        fake = SimpleNamespace(spec_rows=lambda **kw: rows)
        with patch.object(analytics_nodes, "backend", return_value=fake):
            return analytics_nodes.prepare(state)

    def test_a_large_registry_is_cut_to_the_character_budget(self) -> None:
        result = self._prepare(self._rows(2_000), {})
        rendered = json.dumps(result["spec_registry"])
        self.assertLessEqual(len(rendered), get_limits().analytics_registry_chars * 1.1)
        self.assertLess(len(result["spec_registry"]), 2_000)
        self.assertIn("SELECT DISTINCT spec_id", result["registry_note"])

    def test_canonical_specs_survive_the_cut(self) -> None:
        rows = self._rows(2_000, canonical_from=1_999)
        result = self._prepare(rows, {})
        kept = {row["spec_id"] for row in result["spec_registry"]}
        # spec_1999 has canonical status; without the ordering rule its low
        # position would drop it even though it is the comparable one.
        self.assertIn("spec_1999", kept)

    def test_a_small_registry_is_passed_through_whole(self) -> None:
        result = self._prepare(self._rows(5), {})
        self.assertEqual(5, len(result["spec_registry"]))
        self.assertNotIn("truncated", result["registry_note"])

    def test_a_family_scopes_the_backend_lookup(self) -> None:
        seen: dict[str, Any] = {}

        def list_specs(**kw):
            seen.update(kw)
            return self._rows(3)

        fake = SimpleNamespace(spec_rows=list_specs)
        with patch.object(analytics_nodes, "backend", return_value=fake):
            result = analytics_nodes.prepare({"family": "MCCB"})
        self.assertEqual({"family": "MCCB"}, seen)
        self.assertIn("MCCB", result["registry_note"])


class ReadOnlySqlTests(unittest.TestCase):
    """The guard on the analytics tool, which used to reject every CTE.

    Two copies of this rule existed and drifted: the fixtures backend allowed
    WITH, the tool the live runs use did not, so nothing here caught it.
    """

    def _error(self, sql: str) -> str | None:
        return read_only_sql_error(sql.strip().rstrip(";"))

    def test_a_cte_is_one_read_only_query(self) -> None:
        sql = (
            "WITH candidates AS (\n"
            "  SELECT 'CSCS400DM4CO' AS sku_code\n"
            "  UNION ALL SELECT 'CSSD400DM4CO'\n"
            ")\n"
            "SELECT f.sku_code, f.price_inr FROM sku_fact f "
            "JOIN candidates c ON c.sku_code = f.sku_code"
        )
        self.assertIsNone(self._error(sql))

    def test_the_tool_runs_a_cte_rather_than_refusing_it(self) -> None:
        seen: dict[str, str] = {}
        fake = SimpleNamespace(
            execute_sql=lambda sql: seen.setdefault("sql", sql) and {"rows": []}
        )
        with patch.object(analytics_nodes, "backend", return_value=fake):
            result = analytics_nodes.execute_analytics_sql(
                "WITH x AS (SELECT 1 AS n) SELECT n FROM x;"
            )
        self.assertNotIn("error", result)
        self.assertTrue(seen["sql"].startswith("WITH"))
        self.assertFalse(seen["sql"].endswith(";"))

    def test_plain_select_and_values_still_pass(self) -> None:
        self.assertIsNone(self._error("SELECT count(DISTINCT sku_code) FROM sku_fact"))
        self.assertIsNone(self._error("  values (1), (2)"))

    def test_a_write_is_refused_wherever_it_sits(self) -> None:
        for sql in (
            "DELETE FROM sku_fact",
            "WITH gone AS (DELETE FROM sku_fact RETURNING sku_code) SELECT * FROM gone",
            "CREATE TABLE t AS SELECT 1",
            "REPLACE INTO sku_fact VALUES (1)",
            "PRAGMA writable_schema = 1",
        ):
            self.assertIsNotNone(self._error(sql), msg=sql)

    def test_a_write_word_inside_an_expression_is_not_a_write(self) -> None:
        # coalesce(replace(...)) puts `replace` right after an open paren, and
        # a LIKE pattern can hold any keyword at all; neither is a statement.
        self.assertIsNone(
            self._error(
                "SELECT coalesce(replace(value_display, ',', ''), '') AS v "
                "FROM sku_fact WHERE spec_label LIKE '%update; drop%'"
            )
        )
        self.assertIsNone(self._error("SELECT create_date FROM sku_fact"))

    def test_a_second_statement_is_named_as_the_fault(self) -> None:
        error = self._error("SELECT 1; SELECT 2")
        self.assertIsNotNone(error)
        # The two rejections must read differently: a single message sent the
        # analyst back with nothing to change, and it re-sent the same SQL.
        self.assertNotEqual(error, self._error("DELETE FROM sku_fact"))
        self.assertIn(";", error)

    def test_the_fixtures_backend_applies_the_same_rule(self) -> None:
        backend = FixturesBackend()
        self.assertNotIn("error", backend.execute_sql("WITH x AS (SELECT 1) SELECT 1"))
        self.assertIn("error", backend.execute_sql("DROP TABLE sku_fact"))

    def test_the_prompt_and_tool_description_admit_cte(self) -> None:
        prompt = (ROOT / "cs_agent" / "prompts" / "analytics_write_sql.md").read_text()
        self.assertIn("WITH", prompt)
        description = analytics_nodes.ANALYTICS_TOOLS[0].description
        self.assertIn("WITH", description)
        # The backend is SQLite; calling it PostgreSQL invited Postgres-only SQL.
        self.assertNotIn("PostgreSQL", description)


class OutOfScopeTests(unittest.TestCase):
    """A question the catalogue cannot answer must leave before it costs anything.

    "I'm looking for a job in your R&D team" used to reach the planner as a
    product question, dispatch discovery, and spend a tool budget walking the
    taxonomy for a range called R&D. The scope decision rides on the planner
    call that already happens, so the cheap path costs no extra round trip.
    """

    def _plan(self, **kwargs: Any) -> Plan:
        return Plan(intent="i", **kwargs)

    def test_an_out_of_scope_plan_dispatches_nobody(self) -> None:
        plan = self._plan(scope="company", scope_note="a job in the R&D team")
        self.assertEqual([], plan.dispatch)
        self.assertFalse(plan.needs_clarification)

    def test_a_catalogue_plan_must_still_dispatch_somebody(self) -> None:
        """The floor `dispatch` lost as a Field constraint is kept by validator."""
        with self.assertRaises(ValidationError):
            self._plan(scope="catalogue")

    def test_scope_defaults_to_catalogue(self) -> None:
        plan = self._plan(dispatch=[AgentBrief(agent="discovery", objective="map")])
        self.assertEqual("catalogue", plan.scope)

    def test_the_planner_routes_an_out_of_scope_turn_out_of_the_pipeline(self) -> None:
        for scope in ("company", "unrelated"):
            with self.subTest(scope=scope):
                state = {
                    "plan": {"scope": scope, "needs_clarification": False},
                    "dispatch": [],
                    "standalone_question": "q",
                }
                self.assertEqual("out_of_scope", _after_planner(state))

    def test_scope_is_checked_before_clarification(self) -> None:
        """Asking a job applicant for a pole count is worse than not answering."""
        state = {
            "plan": {
                "scope": "company",
                "needs_clarification": True,
                "open_params": ["rated_current"],
            },
            "dispatch": [],
            "clarify_count": 0,
            "standalone_question": "any openings in R&D?",
        }
        self.assertEqual("out_of_scope", _after_planner(state))

    def test_the_node_is_wired_into_the_graph(self) -> None:
        self.assertIn("out_of_scope", set(build_graph().get_graph().nodes))

    def test_the_reply_carries_the_configured_contact_details(self) -> None:
        """They live in config because the routing becomes per-enquiry later."""
        captured: dict[str, Any] = {}

        def _stream(node, messages):
            captured["node"] = node
            captured["system"] = messages[0].content
            captured["user"] = messages[-1].content
            return "Try the website.", False

        contact = get_contact()
        with patch.object(out_of_scope_module, "stream_answer", side_effect=_stream):
            update = out_of_scope_module.out_of_scope(
                {
                    "plan": {"scope": "company", "scope_note": "a job in R&D"},
                    "standalone_question": "I'm looking for a job in your R&D team.",
                    "session": {"turns": []},
                }
            )
        self.assertEqual("out_of_scope", captured["node"])
        self.assertIn(contact.website, captured["system"])
        self.assertIn(contact.phone, captured["system"])
        # The scope and what they actually wanted both reach the model: the
        # reply for a careers enquiry and for a lightbulb are different shapes.
        self.assertIn("company", captured["user"])
        self.assertIn("a job in R&D", captured["user"])
        self.assertEqual("Try the website.", update["draft"])

    def test_an_empty_generation_still_answers_the_user(self) -> None:
        contact = get_contact()
        with patch.object(
            out_of_scope_module, "stream_answer", return_value=("  ", False)
        ):
            update = out_of_scope_module.out_of_scope(
                {"plan": {"scope": "unrelated"}, "standalone_question": "q"}
            )
        self.assertIn(contact.website, update["draft"])
        self.assertIn(contact.phone, update["draft"])

    def test_the_turn_is_recorded_so_a_follow_up_has_context(self) -> None:
        """"What about sales?" needs to know what the previous turn was."""
        with patch.object(
            out_of_scope_module, "stream_answer", return_value=("Call them.", False)
        ):
            update = out_of_scope_module.out_of_scope(
                {
                    "plan": {"scope": "company", "intent": "careers"},
                    "standalone_question": "any R&D jobs?",
                    "session": {"turns": [{"question": "earlier"}]},
                }
            )
        turns = update["session"]["turns"]
        self.assertEqual(2, len(turns))
        self.assertEqual("company", turns[-1]["out_of_scope"])
        self.assertEqual([], turns[-1]["agents_used"])

    def test_the_contact_details_are_overridable_without_editing_a_prompt(self) -> None:
        with patch.dict(os.environ, {"CS_CONTACT_PHONE": "1800-000-0000"}):
            clear_contact_cache()
            self.assertEqual("1800-000-0000", get_contact().phone)
        clear_contact_cache()

    def test_the_planner_prompt_names_every_scope_the_contract_accepts(self) -> None:
        """A value the contract allows but the prompt never mentions is dead."""
        prompt = (ROOT / "cs_agent" / "prompts" / "planner.md").read_text(
            encoding="utf-8"
        )
        for value in ("catalogue", "company", "unrelated"):
            self.assertIn(f'"{value}"', prompt)


class AnswerPresentationTests(unittest.TestCase):
    """The answer should read like a C&S colleague, not like a query result.

    Two habits made it read like a query result: splitting into a catalogue
    section and a general-engineering section, and inventorying every gap the
    specialists recorded whether or not the customer had asked about it.
    """

    def _system_prompt(self, state: dict[str, Any]) -> str:
        captured: dict[str, Any] = {}

        def _stream(node, messages):
            captured["system"] = messages[0].content
            return "answer", False

        with patch.object(composer_module, "stream_answer", side_effect=_stream):
            composer_module.compose_final(state)
        return captured["system"]

    def test_the_composer_is_told_to_write_in_one_voice(self) -> None:
        system = self._system_prompt({"reports": {}, "standalone_question": "q"})
        self.assertIn("One voice, never two", system)
        self.assertNotIn("two clearly labelled sections", system)
        self.assertNotIn("mark it clearly as general engineering practice", system)

    def test_gaps_are_silent_by_default(self) -> None:
        system = self._system_prompt({"reports": {}, "standalone_question": "q"})
        self.assertIn("Silence is the default", system)
        # The old rule surfaced every uncovered part of the question outright.
        self.assertNotIn(
            "If the catalogue does not cover part of the question, say which part",
            system,
        )

    def test_an_absent_description_is_not_announced(self) -> None:
        """Rule 13 stopped invention; announcing the hole is the other half."""
        system = self._system_prompt({"reports": {}, "standalone_question": "q"})
        self.assertIn("announce the absence either", system)
        self.assertIn("fact about the data, not about the product", system)

    def test_a_stopped_retrieval_is_not_a_licence_to_inventory_gaps(self) -> None:
        system = self._system_prompt(
            {
                "reports": {},
                "standalone_question": "q",
                "sufficiency": {"budget_exhausted": True},
            }
        )
        self.assertNotIn("disclose unresolved evidence gaps", system)
        self.assertIn("Retrieval stopped early", system)
        self.assertIn("Rule 10 still", system)


class FixtureToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = FixturesBackend()

    def test_resolve_product_exact(self) -> None:
        result = self.backend.resolve_product(query="WIN2-125-3P-63")
        self.assertEqual("exact", result["resolution"])
        self.assertEqual("WIN2-125-3P-63", result["hits"][0]["sku_code"])

    def test_path_taxonomy_and_spec_registry(self) -> None:
        result = self.backend.taxonomy_browse(path=["protection", "mccb"])
        self.assertTrue(result["children"])
        specs = self.backend.list_canonical_specs(family="WIN2-125")
        self.assertTrue(
            any(row["spec_id"] == "rated_current_a" for row in specs["specs"])
        )

    def test_product_search_v2_envelope(self) -> None:
        result = self.backend.product_search(
            path=["protection", "mccb"],
            family="WIN2",
            filters=[{"spec_id": "rated_current_a", "op": "gte", "value": 125}],
            return_specs=["rated_current_a"],
            limit=10,
        )
        self.assertGreater(result["total_matched"], 0)
        self.assertIn("composite_excluded", result)
        self.assertTrue(result["hits"][0]["specs"])

    def test_price_and_peer_contracts(self) -> None:
        price = self.backend.get_price_detail(["WIN2-125-3P-63"])
        self.assertFalse(price["prices"][0]["quotable"])
        peers = self.backend.get_peer_group("WIN2-125-3P-63")
        self.assertGreaterEqual(len(peers["peers"]), 2)

    def test_compare_uses_catalogue_axes(self) -> None:
        result = self.backend.compare_skus(
            ["WIN2-125-3P-63", "WIN2-125-3P-100"]
        )
        self.assertTrue(result["peer_group_match"])
        self.assertEqual("comparable_on", result["axes_source"])

    def test_document_fixture_is_lexical_and_v2_shaped(self) -> None:
        hits = self.backend.search_documents(
            query="electronic trip",
            path=["protection", "mccb"],
            family="WIN2",
            k=3,
        )
        self.assertTrue(hits)
        self.assertEqual("lexical", hits[0]["mode"])
        self.assertIn("chunk_type", hits[0])

    def test_tool_schemas_and_role_registry(self) -> None:
        args = ProductSearchArgs(
            path=["protection", "mccb"],
            has_chunk_type=["standards"],
        )
        self.assertEqual(["standards"], args.has_chunk_type)
        coerced = ProductSearchArgs(price_status="listed", limit=200)
        self.assertEqual(["listed"], coerced.price_status)
        self.assertEqual(100, coerced.limit)
        docs = SearchDocumentsArgs(
            query="installation",
            family="WIN2",
            chunk_types=["installation"],
        )
        self.assertEqual(["installation"], docs.chunk_types)
        self.assertIn("resolve_product", TOOLS_BY_NAME)
        comparison_names = {tool.name for tool in tools_for_agent("comparison")}
        self.assertIn("compare_skus", comparison_names)
        self.assertIn("analytics_query", comparison_names)

    def test_family_accepts_str_or_list_and_group_by_validates(self) -> None:
        self.assertEqual("WIN2-125", ListCanonicalSpecsArgs(family="WIN2-125").family)
        self.assertEqual(
            ["WIN2-125", "DP09"],
            ListCanonicalSpecsArgs(family=["WIN2-125", "DP09"]).family,
        )
        self.assertIsNone(ListCanonicalSpecsArgs(family=[]).family)
        self.assertEqual("WIN2", ProductSearchArgs(family="WIN2").family)
        self.assertEqual(
            ["WIN2-125", "WIN2-250"],
            ProductSearchArgs(family=["WIN2-125", "WIN2-250"]).family,
        )
        scoped = ProductSearchArgs(group_by="family", family="WIN2")
        self.assertEqual("family", scoped.group_by)
        with self.assertRaises(ValidationError):
            ProductSearchArgs(group_by="sku")
        with self.assertRaises(ValidationError) as caught:
            ProductSearchArgs(group_by="family")
        message = str(caught.exception)
        self.assertIn("family", message.lower())
        self.assertIn("path", message.lower())
        refused = self.backend.product_search(group_by="family")
        self.assertIn("error", refused)
        empty = self.backend.list_canonical_specs(
            family="WIN2-125", spec_id_contains="no_such_spec"
        )
        self.assertEqual([], empty["specs"])
        self.assertNotIn("families_not_found", empty)

    def test_a_spec_only_one_family_has_is_named_not_returned(self) -> None:
        """`poles` is a WIN2-125 spec; DP09 does not carry it."""
        result = self.backend.list_canonical_specs(
            family=["WIN2-125", "DP09"], spec_id_contains="pole"
        )
        self.assertEqual(["DP09", "WIN2-125"], result["scope"]["groups"])
        self.assertEqual([], result["specs"], "not shared, so not returned")
        self.assertEqual(
            {"poles": ["WIN2-125"]}, result["not_shared"]["spec_ids"]
        )

    def test_list_canonical_specs_path_prefix_excludes_contactors(self) -> None:
        result = self.backend.list_canonical_specs(
            path=["protection", "mccb"], spec_id_contains="pole"
        )
        self.assertEqual(
            ["WIN2-125", "WIN2-250", "WIN2-400E"], result["scope"]["groups"]
        )
        poles = next(row for row in result["specs"] if row["spec_id"] == "poles")
        # All three publish it, so it is comparable — and each keeps its own
        # counts rather than a total merged across the three.
        self.assertEqual(
            {"WIN2-125", "WIN2-250", "WIN2-400E"}, set(poles["by_group"])
        )

    def test_list_canonical_specs_string_family_still_finds_rated_current(self) -> None:
        result = self.backend.list_canonical_specs(family="WIN2-125")
        self.assertTrue(
            any(row["spec_id"] == "rated_current_a" for row in result["specs"])
        )
        self.assertEqual(
            {"path": None, "family": "WIN2-125", "group_by": "family",
             "groups": ["WIN2-125"]},
            result["scope"],
        )

    def test_product_search_family_list_and_string_prefix(self) -> None:
        listed = self.backend.product_search(
            family=["WIN2-125", "WIN2-250"],
            filters=[{"spec_id": "poles", "op": "eq", "value": 3}],
        )
        self.assertGreater(listed["total_matched"], 0)
        self.assertTrue(all(hit["family"] == "WIN2-125" for hit in listed["hits"]))
        prefixed = self.backend.product_search(family="WIN2")
        families = {hit["family"] for hit in prefixed["hits"]}
        self.assertTrue({"WIN2-125", "WIN2-250", "WIN2-400E"} <= families)

    def test_product_search_group_by_family_distinguishes_zeros(self) -> None:
        result = self.backend.product_search(
            family=["WIN2-125", "WIN2-250", "DP09"],
            filters=[{"spec_id": "poles", "op": "eq", "value": 3}],
            group_by="family",
        )
        groups = {group["family"]: group for group in result["groups"]}
        self.assertEqual({"WIN2-125", "WIN2-250", "DP09"}, set(groups))
        self.assertGreater(groups["WIN2-125"]["matched"], 0)
        self.assertTrue(groups["WIN2-125"]["spec_present"])
        self.assertEqual(0, groups["WIN2-250"]["matched"])
        self.assertTrue(groups["WIN2-250"]["spec_present"])
        self.assertEqual(0, groups["DP09"]["matched"])
        self.assertFalse(groups["DP09"]["spec_present"])
        self.assertEqual(
            sum(group["matched"] for group in result["groups"]),
            result["total_matched"],
        )

    def test_product_search_group_by_level_uses_path_scope(self) -> None:
        result = self.backend.product_search(
            path=["protection"],
            filters=[{"spec_id": "poles", "op": "eq", "value": 3}],
            group_by="product_group",
        )
        self.assertEqual(["mccb"], [group["product_group"] for group in result["groups"]])
        group = result["groups"][0]
        self.assertTrue(group["spec_present"])
        self.assertGreater(group["matched"], 0)
        self.assertGreater(group["total_in_scope"], group["matched"])
        self.assertTrue(all(hit["path"][0] == "protection" for hit in group["sample_hits"]))

    def test_unknown_family_is_not_a_zero_group(self) -> None:
        result = self.backend.product_search(
            family=["WIN2-125", "NoSuchFamily"],
            filters=[{"spec_id": "poles", "op": "eq", "value": 3}],
            group_by="family",
        )
        self.assertEqual(["WIN2-125"], [group["family"] for group in result["groups"]])
        self.assertEqual(["NoSuchFamily"], result["families_not_found"])

    def test_known_families_reads_the_flat_spec_rows(self) -> None:
        from cs_agent.tools import impl

        with patch.object(impl, "backend", return_value=self.backend):
            impl._known_families.cache_clear()
            names = impl._known_families()
        self.assertIn("WIN2-125", names)
        self.assertIn("DP09", names)


class MangledStreamTests(unittest.TestCase):
    """A streamed tool call whose name no bound tool has.

    Ollama's incremental tool-call parser is less robust than its batch one.
    Asked "What do you have in wim trip?", qwen3.8 emitted its call in Qwen's
    XML form and the streamed parse split `catalogue_map` into two calls —
    `cat\n</parameter` and `alogue_map`. The identical question with
    `CS_STREAM_AGENTS=false` answered correctly on the first call.
    """

    def test_a_name_no_bound_tool_has_is_mangled(self) -> None:
        message = AIMessage(
            content="",
            tool_calls=[
                {"name": "cat\n</parameter", "args": {}, "id": "1"},
                {"name": "alogue_map", "args": {"path_text": "wim trip"}, "id": "2"},
            ],
        )
        self.assertEqual(
            ["cat\n</parameter", "alogue_map"],
            streaming._mangled_calls(message, {"catalogue_map", "taxonomy_browse"}),
        )

    def test_a_real_call_is_left_alone(self) -> None:
        message = AIMessage(
            content="",
            tool_calls=[{"name": "catalogue_map", "args": {}, "id": "1"}],
        )
        self.assertEqual([], streaming._mangled_calls(message, {"catalogue_map"}))
        self.assertEqual([], streaming._mangled_calls(AIMessage(content="hi"), {"x"}))

    def test_generate_retries_unstreamed_when_the_parse_is_mangled(self) -> None:
        good = AIMessage(
            content="",
            tool_calls=[
                {"name": "catalogue_map", "args": {"path_text": "wim trip"}, "id": "1"}
            ],
        )
        model = _StreamingModel(
            tool_call_chunks=[
                {"name": "cat\n</parameter", "args": "", "id": "1", "index": 0},
                {"name": "alogue_map", "args": "{}", "id": "2", "index": 1},
            ],
            invoke_result=good,
        )
        with _screen() as lines:
            message, _ = streaming.generate(
                model, [], label="discovery", tool_names={"catalogue_map"}
            )
        self.assertTrue(model.invoked)
        self.assertEqual("catalogue_map", message.tool_calls[0]["name"])
        del lines

    def test_a_clean_stream_is_not_re_run(self) -> None:
        """The retry must cost nothing on the turns that were already fine."""
        model = _StreamingModel(
            tool_call_chunks=[
                {"name": "catalogue_map", "args": "{}", "id": "1", "index": 0}
            ]
        )
        with _screen():
            streaming.generate(
                model, [], label="discovery", tool_names={"catalogue_map"}
            )
        self.assertFalse(model.invoked)

    def test_without_tool_names_nothing_is_checked(self) -> None:
        """compose_final streams prose and binds no tools; leave it alone."""
        model = _StreamingModel(
            tool_call_chunks=[{"name": "nonsense", "args": "{}", "id": "1", "index": 0}]
        )
        with _screen():
            streaming.generate(model, [], label="discovery")
        self.assertFalse(model.invoked)

    def test_the_reparse_is_recorded_in_the_trace(self) -> None:
        model = _StreamingModel(
            tool_call_chunks=[
                {"name": "alogue_map", "args": "{}", "id": "1", "index": 0}
            ]
        )
        with _screen() as lines:
            streaming.generate(
                model, [], label="discovery", tool_names={"catalogue_map"}
            )
        self.assertIn("llm.stream_reparse", [name for name, _ in lines.events])


class RepeatedFailureTests(unittest.TestCase):
    """A repeat short-circuit must never launder a failure into a success.

    `_earlier_calls` used to record every call regardless of outcome, so the
    second identical *failed* call came back as a plain success message with no
    `error` field. `tool_failures` therefore stopped rising and the failure
    limit never tripped: one run spent 443 short-circuits on a single malformed
    tool call and stopped only when the operator interrupted it.
    """

    def _messages(self):
        call = AIMessage(
            content="",
            tool_calls=[
                {"name": "bad_tool", "args": {}, "id": "1"},
                {"name": "catalogue_map", "args": {"path_text": "x"}, "id": "2"},
            ],
        )
        return [
            call,
            ToolMessage(
                content="Error: bad_tool is not a valid tool",
                tool_call_id="1",
                name="bad_tool",
                status="error",
            ),
            ToolMessage(content='{"groups": []}', tool_call_id="2", name="catalogue_map"),
            call,
        ]

    def test_a_failed_call_is_not_short_circuited(self) -> None:
        seen = tool_node_module._earlier_calls(self._messages())
        self.assertFalse(any("bad_tool" in key for key in seen))

    def test_a_successful_call_still_is(self) -> None:
        seen = tool_node_module._earlier_calls(self._messages())
        self.assertTrue(any("catalogue_map" in key for key in seen))

    def test_a_repeated_failure_keeps_counting_against_the_budget(self) -> None:
        """Re-running costs the same error again, and the limit ends it."""
        messages = self._messages()
        replayed = ToolMessage(
            content="Error: bad_tool is not a valid tool",
            tool_call_id="3",
            name="bad_tool",
            status="error",
        )
        self.assertEqual(1, count_failures([replayed]))
        self.assertEqual(1, count_failures(trailing_tool_messages(messages[:3])))


    def test_a_mangled_name_is_rejected_with_the_tool_it_meant(self) -> None:
        """LangGraph's own message lists nine tools and stops there."""
        from cs_agent.subgraphs.agents.tool_node import make_tool_node

        bound = [TOOLS_BY_NAME["catalogue_map"], TOOLS_BY_NAME["get_sku"]]
        result = make_tool_node(bound)(
            {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "cat\n</parameter", "args": {}, "id": "c1"}
                        ],
                    )
                ]
            }
        )
        message = result["messages"][0]
        payload = json.loads(message.content)
        self.assertEqual("error", message.status)
        self.assertIn("catalogue_map", payload["error"])
        self.assertIn("malformed", payload["error"])
        self.assertEqual(1, count_failures(result["messages"]))

    def test_an_ambiguous_fragment_suggests_nothing(self) -> None:
        """Naming the wrong tool is worse than naming none."""
        from cs_agent.subgraphs.agents.tool_node import _did_you_mean

        self.assertIsNone(_did_you_mean("get", ["get_sku", "get_price_detail"]))
        self.assertIsNone(_did_you_mean("!!", ["get_sku"]))
        self.assertEqual("get_sku", _did_you_mean("t_sk", ["get_sku", "product_search"]))

    def test_valid_calls_in_the_same_batch_still_run(self) -> None:
        """One malformed call must not discard the retrieval beside it."""
        from cs_agent.subgraphs.agents.tool_node import make_tool_node

        sent: list[Any] = []

        def _fake(state, config=None):
            sent.extend(state["messages"][-1].tool_calls)
            return {"messages": [ToolMessage(content="{}", tool_call_id="c2")]}

        with patch(
            "cs_agent.subgraphs.agents.tool_node.ToolNode",
            return_value=SimpleNamespace(invoke=_fake),
        ):
            result = make_tool_node([SimpleNamespace(name="catalogue_map")])(
                {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {"name": "alogue_map", "args": {}, "id": "c1"},
                                {
                                    "name": "catalogue_map",
                                    "args": {"path_text": "wintrip"},
                                    "id": "c2",
                                },
                            ],
                        )
                    ]
                }
            )
        self.assertEqual(["c2"], [call["id"] for call in sent])
        self.assertEqual({"c1", "c2"}, {m.tool_call_id for m in result["messages"]})


class CatalogueMapTests(unittest.TestCase):
    """The tool that answers "what X do you have" without walking the tree.

    "What wintrip products do you have" used to cost a product_search that
    matched nothing, then a taxonomy_browse from the root, then another to walk
    into the branch it guessed — four calls to learn a fact the path column
    already held.
    """

    def setUp(self) -> None:
        self.backend = FixturesBackend()

    def test_path_text_finds_a_branch_without_knowing_its_path(self) -> None:
        result = self.backend.catalogue_map(path_text="mccb")
        self.assertTrue(result["groups"])
        self.assertTrue(
            all("mccb" in " > ".join(g["path"]).lower() for g in result["groups"])
        )
        self.assertEqual(
            sum(g["sku_count"] for g in result["groups"]), result["total_skus"]
        )

    def test_groups_break_down_by_the_level_columns(self) -> None:
        """Grouped on division / product_group / ... , not on rendered path text.

        Those columns are what the rest of the toolchain takes as arguments, so
        the tool hands back the real values rather than a re-split string.
        """
        group = self.backend.catalogue_map(path_text="WIN2-125")["groups"][0]
        self.assertEqual("protection", group["division"])
        self.assertEqual("mccb", group["product_group"])
        self.assertEqual("WIN2-125", group["product_subgroup"])
        self.assertEqual("WIN2-125", group["family"])
        self.assertEqual(2, group["sku_count"])
        self.assertIn("description", group)

    def test_a_level_the_branch_never_reaches_is_omitted(self) -> None:
        """'N/A' is build padding for an absent level, not a category name."""
        group = self.backend.catalogue_map(path_text="WIN2-125")["groups"][0]
        self.assertNotIn("product_range", group)
        self.assertNotIn("N/A", group.values())

    def test_path_stays_alongside_the_levels_for_the_next_call(self) -> None:
        """taxonomy_browse and product_search take a list of literal values."""
        group = self.backend.catalogue_map(path_text="WIN2-125")["groups"][0]
        self.assertEqual(["protection", "mccb", "WIN2-125"], group["path"])
        levels = [
            group[column]
            for column in ("division", "product_group", "product_subgroup")
        ]
        self.assertEqual(levels, group["path"])

    def test_market_segment_filters_to_the_tagged_branches(self) -> None:
        result = self.backend.catalogue_map(market_segment="Residential")
        self.assertTrue(result["groups"])
        for group in result["groups"]:
            self.assertIn("Residential", group["market_segments"])
        # The segment tag is coarse on purpose; every contactor branch carries it
        # and no breaker branch does.
        self.assertTrue(
            all(g["product_group"] == "contactor" for g in result["groups"])
        )

    def test_both_filters_narrow_rather_than_widen(self) -> None:
        both = self.backend.catalogue_map(
            path_text="DP09", market_segment="Residential"
        )
        self.assertEqual(1, both["total_groups"])
        none = self.backend.catalogue_map(
            path_text="DP09", market_segment="Agriculture"
        )
        self.assertEqual(0, none["total_groups"])

    def test_neither_filter_is_a_schema_error_naming_the_fix(self) -> None:
        """An unfiltered call would dump the whole taxonomy for no question."""
        with self.assertRaises(ValidationError) as caught:
            CatalogueMapArgs()
        message = str(caught.exception)
        self.assertIn("path_text", message)
        self.assertIn("market_segment", message)
        self.assertIn("taxonomy_browse", message)

    def test_a_blank_string_counts_as_no_filter(self) -> None:
        with self.assertRaises(ValidationError):
            CatalogueMapArgs(path_text="   ", market_segment="")

    def test_an_empty_result_says_what_to_try_instead(self) -> None:
        """A silent empty result is what makes a specialist guess again."""
        miss = self.backend.catalogue_map(path_text="wintrip")
        self.assertEqual([], miss["groups"])
        self.assertTrue(miss["no_match"]["closest_paths"])
        segment = self.backend.catalogue_map(market_segment="Domestic")
        self.assertIn("Industries", segment["no_match"]["known_market_segments"])

    def test_matched_on_reports_only_the_filters_used(self) -> None:
        result = self.backend.catalogue_map(path_text="mccb")
        self.assertEqual({"path_text": "mccb"}, result["matched_on"])

    def test_limit_caps_the_rows_not_the_totals(self) -> None:
        capped = self.backend.catalogue_map(path_text="protection", limit=1)
        self.assertEqual(1, len(capped["groups"]))
        self.assertEqual(3, capped["total_groups"])

    def test_every_specialist_can_reach_it(self) -> None:
        for agent in (
            "discovery",
            "spec_selection",
            "solution_advisory",
            "comparison",
            "compliance",
        ):
            names = {tool.name for tool in tools_for_agent(agent)}
            self.assertIn("catalogue_map", names, agent)

    def test_the_description_documents_the_segment_vocabulary(self) -> None:
        """market_segment existed on taxonomy_browse but was never described,
        so the model never used it and walked the taxonomy by hand instead."""
        from cs_agent.tools import descriptions

        for text in (descriptions.TAXONOMY_BROWSE, descriptions.CATALOGUE_MAP):
            self.assertIn("market_segment", text)
            self.assertIn("Residential", text)
            self.assertIn("Agriculture", text)
        self.assertIn("market_segment", descriptions.PRODUCT_SEARCH)


class GraphTests(unittest.TestCase):
    def test_graph_topology(self) -> None:
        nodes = set(build_graph().get_graph().nodes)
        self.assertTrue(
            {
                "intake", "planner", "clarify", "specialist", "gate",
                "composer", "compose_final",
            } <= nodes
        )
        self.assertNotIn("validator", nodes)

    def test_all_specialist_graphs_build_with_private_messages(self) -> None:
        for agent in (
            "discovery",
            "spec_selection",
            "solution_advisory",
            "comparison",
            "compliance",
        ):
            nodes = set(build_specialist_graph(agent).get_graph().nodes)
            self.assertTrue({"prepare", "agent", "tools", "record", "report"} <= nodes)

    def test_specialist_runtime_error_becomes_partial_report(self) -> None:
        brief = AgentBrief(
            agent="discovery",
            objective="map MCCBs",
            allowance=4,
        ).model_dump()
        with patch(
            "cs_agent.graph.build.build_specialist_graph",
            side_effect=RuntimeError("XML syntax error"),
        ):
            update = _run_specialist(
                {"brief": brief, "standalone_question": "What MCBs do you have?"}
            )
        report = update["reports"]["discovery"]
        self.assertEqual("partial", report["status"])
        self.assertTrue(report["gaps"])

    def test_planner_dispatches_only_the_first_stage(self) -> None:
        state = {
            "plan": {"needs_clarification": False},
            "dispatch": [
                AgentBrief(
                    agent="discovery", objective="map MCCBs", stage=1, depth="detailed"
                ).model_dump(),
                AgentBrief(
                    agent="spec_selection", objective="filter MCCBs", stage=2
                ).model_dump(),
            ],
            "standalone_question": "show MCCBs",
            "tool_calls_made": 0,
            "turn_tool_calls_start": 0,
        }
        sends = _after_planner(state)
        self.assertEqual(1, len(sends))
        self.assertEqual("specialist", sends[0].node)
        self.assertEqual("discovery", sends[0].arg["brief"]["agent"])
        # The whole per-agent budget, not a share split with a stage that has
        # not started; stage two is sized from what stage one leaves behind.
        self.assertEqual(
            get_limits().per_agent_tool_budget, sends[0].arg["brief"]["allowance"]
        )

    def test_gate_starts_the_next_stage_with_upstream_findings(self) -> None:
        discovery = DiscoveryReport(
            agent="discovery",
            status="complete",
            summary="Two MCCB families",
            families=[FamilyBrief(name="MCCB – Wintrip", sku_count=42)],
            representative_skus=["WT-100"],
        ).model_dump()
        state = {
            "gate_result": {"ok": True, "failures": []},
            "gate_retries": {},
            "stage_index": 1,
            "reports": {"discovery": discovery},
            "dispatch": [
                AgentBrief(agent="discovery", objective="map", stage=1).model_dump(),
                AgentBrief(
                    agent="spec_selection", objective="shortlist", stage=2
                ).model_dump(),
            ],
            "standalone_question": "best MCB for a leather factory",
            "tool_calls_made": 6,
            "turn_tool_calls_start": 0,
        }
        sends = _after_gate(state)
        self.assertEqual(1, len(sends))
        self.assertEqual("spec_selection", sends[0].arg["brief"]["agent"])
        upstream = sends[0].arg["upstream"]
        self.assertIn("discovery", upstream)
        self.assertEqual(["WT-100"], upstream["discovery"]["representative_skus"])

    def test_gate_composes_after_the_last_stage(self) -> None:
        state = {
            "gate_result": {"ok": True, "failures": []},
            "gate_retries": {},
            "stage_index": 2,
            "dispatch": [
                AgentBrief(agent="discovery", objective="map", stage=1).model_dump(),
                AgentBrief(
                    agent="spec_selection", objective="shortlist", stage=2
                ).model_dump(),
            ],
            "standalone_question": "q",
            "tool_calls_made": 6,
            "turn_tool_calls_start": 0,
        }
        self.assertEqual("composer", _after_gate(state))

    def test_gate_retry_is_targeted(self) -> None:
        state = {
            "gate_result": {
                "ok": False,
                "failures": [
                    {"agent": "discovery", "violations": ["needs SKU"]}
                ],
            },
            "gate_retries": {"1": 1},
            "stage_index": 1,
            "dispatch": [
                AgentBrief(agent="discovery", objective="map", stage=1).model_dump()
            ],
            "standalone_question": "map",
            "tool_calls_made": 0,
            "turn_tool_calls_start": 0,
        }
        sends = _after_gate(state)
        self.assertEqual(1, len(sends))
        self.assertIn("needs SKU", sends[0].arg["brief"]["revision_note"])
        self.assertEqual(1, sends[0].arg["brief"]["stage"])

    def test_exhausted_retries_do_not_block_the_next_stage(self) -> None:
        state = {
            "gate_result": {
                "ok": False,
                "failures": [{"agent": "discovery", "violations": ["needs SKU"]}],
            },
            "gate_retries": {"1": 2},
            "stage_index": 1,
            "reports": {},
            "dispatch": [
                AgentBrief(agent="discovery", objective="map", stage=1).model_dump(),
                AgentBrief(
                    agent="spec_selection", objective="shortlist", stage=2
                ).model_dump(),
            ],
            "standalone_question": "q",
            "tool_calls_made": 0,
            "turn_tool_calls_start": 0,
        }
        sends = _after_gate(state)
        self.assertEqual(1, len(sends))
        self.assertEqual("spec_selection", sends[0].arg["brief"]["agent"])

    def test_composer_revision_is_targeted(self) -> None:
        state = {
            "sufficiency": {
                "sufficient": False,
                "revision_allowed": True,
                "gaps": [{
                    "agent": "compliance",
                    "missing": "IEC source",
                    "suggested_tool": "search_documents",
                }],
            },
            "dispatch": [
                AgentBrief(
                    agent="compliance", objective="check IEC", stage=1
                ).model_dump()
            ],
            "stage_index": 1,
            "standalone_question": "IEC?",
            "tool_calls_made": 0,
            "turn_tool_calls_start": 0,
        }
        sends = _after_composer(state)
        self.assertEqual(1, len(sends))
        self.assertEqual("compliance", sends[0].arg["brief"]["agent"])

    def test_first_turn_intake_needs_no_model(self) -> None:
        module = importlib.import_module("cs_agent.graph.nodes.intake")
        result = module.intake(
            {
                "messages": [HumanMessage(content="Show MCCBs")],
                "session": {"turns": []},
                "tool_calls_made": 0,
            }
        )
        self.assertEqual("Show MCCBs", result["standalone_question"])
        self.assertFalse(result["is_followup"])

    def test_followup_intake_carries_session(self) -> None:
        module = importlib.import_module("cs_agent.graph.nodes.intake")
        fake = type("Fake", (), {
            "standalone_question": "Compare SKU-A with SKU-B",
            "referenced_skus": ["SKU-A"],
            "is_followup": True,
            "carried_params": {"voltage_v": 415},
        })()
        with patch.object(module, "structured", return_value=fake):
            result = module.intake(
                {
                    "messages": [HumanMessage(content="compare that to SKU-B")],
                    "session": {
                        "turns": [{"question": "SKU-A"}],
                        "focus_skus": ["SKU-A"],
                        "resolved_params": {},
                    },
                    "tool_calls_made": 4,
                }
            )
        self.assertTrue(result["is_followup"])
        self.assertEqual(415, result["session"]["resolved_params"]["voltage_v"])
        self.assertEqual(4, result["turn_tool_calls_start"])

    def test_initial_state_is_v2(self) -> None:
        state = _initial_state("question")
        self.assertIn("session", state)
        self.assertIn("reports", state)
        self.assertEqual(0, state["revision_round"])

    def test_planner_receives_clarification_answers(self) -> None:
        module = importlib.import_module("cs_agent.graph.nodes.planner")
        captured: dict[str, Any] = {}

        def fake_structured(_role, messages, _schema):
            captured["content"] = messages[1].content
            return Plan(
                intent="size protection",
                dispatch=[
                    AgentBrief(agent="discovery", objective="map isolators")
                ],
                known_params={},
                open_params=["System Voltage (DC string voltage)"],
                needs_clarification=True,
            )

        with patch.object(module, "structured", side_effect=fake_structured):
            result = module.planner(
                {
                    "standalone_question": (
                        "What's the right protection setup for a rooftop solar "
                        "feed into my building's main panel?"
                    ),
                    "session": {
                        "resolved_params": {
                            "clarification": "Rated current 200 A, 4 poles, fixed"
                        }
                    },
                    "plan": {
                        "open_params": ["System Voltage (DC string voltage)"],
                        "needs_clarification": True,
                    },
                    "clarify_count": 1,
                    "tool_calls_made": 0,
                    "turn_tool_calls_start": 0,
                    "assumptions": [],
                }
            )
        self.assertIn("200 A", captured["content"])
        self.assertIn("4 poles", captured["content"])
        self.assertIn("200 A", result["standalone_question"])
        self.assertEqual(
            "Rated current 200 A, 4 poles, fixed",
            result["dispatch"][0]["parameters"]["clarification"],
        )
        self.assertIn("user-provided parameters", result["assumptions"][0].lower())

    def test_clarify_folds_answers_into_the_question(self) -> None:
        module = importlib.import_module("cs_agent.graph.nodes.clarify")
        fake_model = SimpleNamespace(
            invoke=lambda _msgs: SimpleNamespace(
                content="1. What is the DC string voltage? (600)"
            )
        )
        with (
            patch.object(module, "get_model", return_value=fake_model),
            patch.object(
                module, "interrupt", return_value="Rated current 200 A, 4 poles, fixed"
            ),
        ):
            result = module.clarify(
                {
                    "plan": {
                        "open_params": ["System Voltage (DC string voltage)"],
                        "known_params": {},
                    },
                    "standalone_question": (
                        "What's the right protection setup for a rooftop solar feed?"
                    ),
                    "session": {"resolved_params": {}},
                    "clarify_count": 0,
                }
            )
        self.assertIn("200 A", result["standalone_question"])
        self.assertEqual(
            "Rated current 200 A, 4 poles, fixed",
            result["session"]["resolved_params"]["clarification"],
        )
        self.assertEqual(1, result["clarify_count"])

    def test_clarify_skips_params_already_answered(self) -> None:
        module = importlib.import_module("cs_agent.graph.nodes.clarify")
        with (
            patch.object(module, "get_model") as get_model,
            patch.object(module, "interrupt") as interrupt,
        ):
            result = module.clarify(
                {
                    "plan": {
                        "open_params": ["rated_current_a", "poles"],
                        "known_params": {},
                    },
                    "standalone_question": "size a main breaker",
                    "session": {
                        "resolved_params": {
                            "rated_current_a": 200,
                            "poles": 4,
                        }
                    },
                    "clarify_count": 1,
                }
            )
        get_model.assert_not_called()
        interrupt.assert_not_called()
        self.assertFalse(result["plan"]["needs_clarification"])
        self.assertIn("200", result["standalone_question"])

    def test_specialist_send_includes_resolved_params(self) -> None:
        state = {
            "plan": {"needs_clarification": False, "known_params": {}},
            "dispatch": [
                AgentBrief(
                    agent="discovery",
                    objective="map MCCBs",
                ).model_dump(),
            ],
            "standalone_question": "solar feed protection",
            "session": {
                "resolved_params": {"rated_current_a": 200, "poles": 4}
            },
            "tool_calls_made": 0,
            "turn_tool_calls_start": 0,
        }
        sends = _after_planner(state)
        self.assertEqual(1, len(sends))
        self.assertEqual(200, sends[0].arg["brief"]["parameters"]["rated_current_a"])
        self.assertEqual(4, sends[0].arg["brief"]["parameters"]["poles"])


class TraceLabellingTests(unittest.TestCase):
    """Parallel specialists must be distinguishable in the trace."""

    def test_scoped_config_nests_labels(self) -> None:
        outer = agent_scoped_config("discovery")
        self.assertEqual("discovery", outer["metadata"][AGENT_METADATA_KEY])
        inner = agent_scoped_config("analytics", outer)
        self.assertEqual("discovery/analytics", inner["metadata"][AGENT_METADATA_KEY])

    def test_tool_events_carry_the_calling_agent(self) -> None:
        events: list[dict[str, Any]] = []
        trace = SimpleNamespace(event=lambda name, **fields: events.append(
            {"event": name, **fields}
        ))
        handler = AgentCallbackHandler(trace)
        run_id = uuid.uuid4()
        handler.on_tool_start(
            {"name": "sku_lookup"},
            "{}",
            run_id=run_id,
            metadata={AGENT_METADATA_KEY: "compliance"},
        )
        handler.on_tool_end({"rows": []}, run_id=run_id)
        self.assertEqual(["compliance", "compliance"], [e["agent"] for e in events])

    def test_agent_is_inherited_from_the_parent_run(self) -> None:
        handler = AgentCallbackHandler(SimpleNamespace(event=lambda *a, **k: None))
        parent = uuid.uuid4()
        child = uuid.uuid4()
        handler.on_chain_start(
            None, {}, run_id=parent, metadata={AGENT_METADATA_KEY: "pricing"}
        )
        handler.on_tool_start(
            {"name": "sku_lookup"}, "{}", run_id=child, parent_run_id=parent
        )
        self.assertEqual("pricing", handler._run_agents[child])


class DatabaseDefinitionTests(unittest.TestCase):
    def test_v2_sql_contains_all_views_and_indexes(self) -> None:
        sql = (ROOT / "cs_agent" / "db" / "views.sql").read_text()
        for view in (
            "mv_sku", "mv_code_alias", "mv_fact", "mv_price", "mv_source",
            "mv_spec_registry", "mv_facet", "mv_chunk_index",
        ):
            self.assertIn(f"CREATE MATERIALIZED VIEW in_use.{view}", sql)
        self.assertIn("vector(768)", sql)
        self.assertIn("content_tsv", sql)

    def test_default_make_target_runs_every_suite(self) -> None:
        """Vector retrieval is a shipped code path, so it is not opt-in.

        The embeddings are built into the artifact now; a silent skip would let
        a regression in vector search reach a live run unnoticed.
        """
        makefile = (ROOT / "Makefile").read_text()
        test_target = makefile.split("\ntest:", 1)[1].split("\ntest-vector:", 1)[0]
        for suite in (
            "tests.test_framework",
            "tests.test_sqlite",
            "tests.test_vector_retrieval",
        ):
            self.assertIn(suite, test_target)

    def test_vector_suite_runs_unless_explicitly_skipped(self) -> None:
        source = (ROOT / "tests" / "test_vector_retrieval.py").read_text()
        self.assertIn("CS_SKIP_VECTOR_TESTS", source)
        self.assertNotIn("skipUnless", source)


class PhraseTests(unittest.TestCase):
    """The chat window's progress lines, built from trace records."""

    def test_the_named_argument_becomes_the_sentence(self) -> None:
        from cs_agent.ui.phrases import tool_phrase

        self.assertEqual(
            tool_phrase("catalogue_map", {"path_text": "MCB"}),
            "Searching the catalogue for MCB",
        )
        self.assertEqual(
            tool_phrase("product_search", {"text": "MCB solar", "limit": 20}),
            "Searching products for MCB solar",
        )

    def test_the_first_argument_present_wins(self) -> None:
        """Ordering in the table is the priority, so the specific one is used."""
        from cs_agent.ui.phrases import tool_phrase

        phrase = tool_phrase(
            "catalogue_map", {"path_text": "MCB", "market_segment": "Residential"}
        )
        self.assertEqual(phrase, "Searching the catalogue for MCB")

    def test_an_empty_path_reads_as_the_top_of_the_tree(self) -> None:
        """`taxonomy_browse(path=[])` is the call that lists the divisions."""
        from cs_agent.ui.phrases import tool_phrase

        self.assertEqual(
            tool_phrase("taxonomy_browse", {"path": []}),
            "Opening the top of the catalogue",
        )
        self.assertEqual(
            tool_phrase("taxonomy_browse", {"path": ["Low Voltage", "Breakers"]}),
            "Opening Low Voltage > Breakers",
        )

    def test_every_specialist_is_named_in_its_progress_line(self) -> None:
        from cs_agent.tools.registry import AGENT_TOOL_NAMES
        from cs_agent.ui.phrases import agent_phrase, report_phrase

        for agent in AGENT_TOOL_NAMES:
            with self.subTest(agent=agent):
                self.assertIsNotNone(agent_phrase(agent), agent)
                self.assertIn("specialist", agent_phrase(agent))
                self.assertIn("evidence report", report_phrase(agent) or "")

    def test_a_tool_the_table_never_heard_of_still_reads(self) -> None:
        from cs_agent.ui.phrases import tool_phrase

        self.assertEqual(tool_phrase("brand_new_tool", {"x": 1}), "Running brand new tool")

    def test_long_values_are_clipped(self) -> None:
        from cs_agent.ui.phrases import tool_phrase

        phrase = tool_phrase("resolve_product", {"query": "x" * 200})
        self.assertLess(len(phrase), 90)
        self.assertTrue(phrase.endswith("\u2026"))

    def test_only_tool_and_node_starts_reach_the_window(self) -> None:
        """Everything else in a trace is bookkeeping and stays in the file."""
        from cs_agent.ui.app import _progress

        self.assertEqual(
            _progress(
                {"event": "tool.start", "tool": "catalogue_map", "inputs": {"path_text": "MCB"}}
            ),
            "Searching the catalogue for MCB",
        )
        self.assertEqual(
            _progress({"event": "node.start", "node": "specialist", "agent": "discovery"}),
            "Discovery specialist — finding what C&S sells here",
        )
        # The specialist subgraph's report node arrives as a runnable, not a
        # graph node, and is the longest generation in a turn.
        self.assertEqual(
            _progress({"event": "runnable.start", "name": "report", "agent": "comparison"}),
            "Comparison specialist is writing its final evidence report",
        )
        self.assertIsNone(
            _progress({"event": "runnable.start", "name": "agent", "agent": "comparison"})
        )
        self.assertEqual(
            _progress({"event": "node.start", "node": "compose_final"}),
            "Writing the answer",
        )
        for noise in ("runnable.start", "llm.end", "state.update", "tool.end"):
            self.assertIsNone(_progress({"event": noise}), noise)


class TraceListenerTests(unittest.TestCase):
    """A second reader of the trace, for a frontend showing progress."""

    def _trace(self, records: list) -> Any:
        from cs_agent.observability import TraceLogger

        return TraceLogger(
            file_path=Path(os.devnull),
            print_to_screen=False,
            listener=records.append,
        )

    def test_the_listener_sees_every_event(self) -> None:
        records: list = []
        trace = self._trace(records)
        try:
            trace.event("tool.start", tool="catalogue_map")
        finally:
            trace.close()
        self.assertEqual([r["event"] for r in records], ["tool.start"])
        self.assertEqual(records[0]["tool"], "catalogue_map")

    def test_notify_reaches_the_listener_but_not_the_file(self) -> None:
        """Answer fragments would double the size of every trace."""
        from cs_agent.observability import TraceLogger

        records: list = []
        import tempfile

        path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        trace = TraceLogger(
            file_path=path / "t.jsonl", print_to_screen=False, listener=records.append
        )
        try:
            trace.notify("answer.delta", text="hello")
        finally:
            trace.close()
        self.assertEqual(records[0]["event"], "answer.delta")
        self.assertEqual(records[0]["text"], "hello")
        self.assertEqual((path / "t.jsonl").read_text().strip(), "")

    def test_no_listener_is_the_normal_case_and_costs_nothing(self) -> None:
        from cs_agent.observability import TraceLogger

        trace = TraceLogger(file_path=Path(os.devnull), print_to_screen=False)
        try:
            self.assertIsNone(trace.listener)
            trace.notify("answer.delta", text="ignored")  # must not raise
        finally:
            trace.close()


class ChatTurnTests(unittest.TestCase):
    """The chat window's turn loop, including the clarification handoff."""

    def setUp(self) -> None:
        # A turn builds its own TraceLogger from the environment, so point it
        # somewhere disposable: these tests must not append to the trace the
        # operator reads, nor scribble over the unittest output.
        import tempfile

        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(
            patch.dict(
                os.environ,
                {
                    "CS_LOG_FILE": str(Path(directory) / "trace.jsonl"),
                    "CS_LOG_TO_SCREEN": "false",
                },
            )
        )

    def _drain(self, message: str, state: dict) -> list:
        from cs_agent.ui.app import respond

        frames = list(respond(message, [], state))
        return frames[-1] if frames else []

    def test_a_finished_turn_shows_the_answer_and_keeps_the_session(self) -> None:
        result = {"draft": "Five WiNtrip ranges.", "session": {"turns": [1]}}
        state: dict = {}
        with patch("cs_agent.ui.app.run_question", return_value=result) as run:
            final = self._drain("what wintrip products?", state)
        self.assertEqual(final[-1].content, "Five WiNtrip ranges.")
        self.assertFalse(state["awaiting"])
        self.assertEqual(state["session"], {"turns": [1]})
        # The frontend never answers the clarify interrupt from inside the turn.
        self.assertIsNone(run.call_args.kwargs["on_clarify"])

    def test_a_clarifying_question_is_asked_in_the_chat(self) -> None:
        """The turn parks on the checkpoint rather than blocking on stdin."""
        interrupt = {"__interrupt__": [SimpleNamespace(value={"questions": ["Rating?"]})]}
        state: dict = {}
        with patch("cs_agent.ui.app.run_question", return_value=interrupt):
            final = self._drain("I need a breaker", state)
        self.assertIn("Rating?", final[-1].content)
        self.assertTrue(state["awaiting"])
        # The paused turn owns the session; overwriting it would lose the thread.
        self.assertNotIn("session", state)

    def test_the_next_message_resumes_the_parked_turn(self) -> None:
        state = {"thread_id": "t-1", "awaiting": True}
        result = {"draft": "A 250 A MCCB.", "session": {}}
        with patch("cs_agent.ui.app.resume_question", return_value=result) as resume:
            with patch("cs_agent.ui.app.run_question") as run:
                final = self._drain("250 A at 415 V", state)
        run.assert_not_called()
        self.assertEqual(resume.call_args.kwargs["thread_id"], "t-1")
        self.assertEqual(final[-1].content, "A 250 A MCCB.")
        self.assertFalse(state["awaiting"])

    def test_progress_steps_are_shown_then_marked_done(self) -> None:
        def fake_run(question, **kwargs):
            trace = kwargs["trace"]
            trace.event("node.start", node="specialist", agent="discovery")
            trace.event(
                "tool.start", tool="catalogue_map", inputs={"path_text": "wintrip"}
            )
            trace.event("runnable.start", name="noise")
            trace.event("runnable.start", name="report", agent="discovery")
            trace.notify("answer.delta", text="Five ranges.")
            return {"draft": "Five ranges.", "session": {}}

        state: dict = {}
        with patch("cs_agent.ui.app.run_question", side_effect=fake_run):
            final = self._drain("what wintrip products?", state)
        titles = [m.metadata["title"] for m in final if (m.metadata or {}).get("title")]
        self.assertEqual(
            titles,
            [
                "Discovery specialist — finding what C&S sells here",
                "Searching the catalogue for wintrip",
                "Discovery specialist is writing its final evidence report",
            ],
        )
        self.assertTrue(all(m.metadata["status"] == "done" for m in final[:-1]))
        self.assertEqual(final[-1].content, "Five ranges.")

    def test_a_failed_turn_says_so_instead_of_hanging(self) -> None:
        state: dict = {}
        with patch("cs_agent.ui.app.run_question", side_effect=RuntimeError("ollama down")):
            final = self._drain("what wintrip products?", state)
        self.assertIn("ollama down", final[-1].content)

    def test_a_cancelled_turn_says_so_rather_than_erroring(self) -> None:
        from cs_agent.ui.app import TurnCancelled

        state: dict = {}
        with patch("cs_agent.ui.app.run_question", side_effect=TurnCancelled):
            final = self._drain("what wintrip products?", state)
        self.assertIn("Stopped", final[-1].content)

    def test_stopping_only_takes_effect_at_the_next_boundary(self) -> None:
        """LangChain drops what a handler raises unless it asks not to."""
        import threading

        from cs_agent.ui.app import _CancelOnDemand, TurnCancelled

        flag = threading.Event()
        handler = _CancelOnDemand(flag)
        self.assertTrue(handler.raise_error)
        handler.on_tool_start({}, "")  # not asked to stop: silent
        flag.set()
        for hook in ("on_chain_start", "on_llm_start", "on_tool_start"):
            with self.subTest(hook=hook):
                with self.assertRaises(TurnCancelled):
                    getattr(handler, hook)({}, "")

    def test_stop_sets_the_flag_the_running_turn_watches(self) -> None:
        import threading

        from cs_agent.ui.app import _stop

        flag = threading.Event()
        _stop({"cancel": flag})
        self.assertTrue(flag.is_set())
        _stop({})  # no turn running: must not raise

    def test_a_new_chat_drops_the_thread_as_well_as_the_transcript(self) -> None:
        """The checkpointer keys on thread_id, so reusing one lets it back in."""
        from cs_agent.ui.app import _reset

        history, state = _reset({"thread_id": "t-1", "session": {"turns": [1]}})
        self.assertEqual(history, [])
        self.assertEqual(state, {})

    def test_a_second_turn_waits_for_an_abandoned_one(self) -> None:
        """Two live turns would fight over the module-level active trace."""
        import threading

        from cs_agent.ui.app import _retire_previous

        released = threading.Event()
        flag = threading.Event()
        worker = threading.Thread(target=lambda: released.wait(5), daemon=True)
        worker.start()
        threading.Timer(0.05, released.set).start()
        _retire_previous({"worker": worker, "cancel": flag})
        self.assertTrue(flag.is_set())
        self.assertFalse(worker.is_alive())

    def test_the_questions_a_turn_stopped_on_are_readable(self) -> None:
        from cs_agent.run import interrupt_questions

        self.assertEqual(interrupt_questions({"draft": "done"}), [])
        self.assertEqual(
            interrupt_questions(
                {"__interrupt__": [SimpleNamespace(value={"questions": ["A?", "B?"]})]}
            ),
            ["A?", "B?"],
        )


if __name__ == "__main__":
    unittest.main()


class ReportModeTests(unittest.TestCase):
    """The specialist report, built without a model call."""

    @staticmethod
    def _tool(name: str, payload: Any) -> ToolMessage:
        return ToolMessage(
            content=json.dumps(payload, default=str),
            tool_call_id=name,
            name=name,
        )

    MAP = {
        "matched_on": {"path_text": "wintrip"},
        "groups": [
            {
                "path": ["Final Distribution Products", "MCB & Isolators", "WiNtrip2 MCB & Isolator"],
                "name": "WiNtrip2 MCB & Isolator",
                "sku_count": 408,
                "description": "With breaking Capacity of 10kA",
                "url": "https://example.invalid/wintrip2",
            },
            {
                "path": ["Final Distribution Products", "MCB & Isolators", "WiNtrip MCB & Isolator"],
                "name": "WiNtrip MCB & Isolator",
                "sku_count": 172,
                "description": "MCB upto 125A",
                "url": "https://example.invalid/wintrip",
            },
        ],
    }
    BROWSE = {
        "path": ["Final Distribution Products"],
        "children": [
            {"name": "Industrial Plugs and Sockets", "sku_count": 62, "is_leaf": True},
            {"name": "MCB & Isolators", "sku_count": 900, "is_leaf": False},
        ],
    }

    def _brief(self, agent: str = "discovery", depth: str = "overview") -> dict[str, Any]:
        return {
            "agent": agent,
            "objective": "Name the WiNtrip ranges.",
            "depth": depth,
            "must_return": ["families"],
            "parameters": {},
        }

    def test_mode_defaults_to_auto(self) -> None:
        """`auto` is the shipped default: derive on overview, model on detailed."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CS_REPORT_MODE", None)
            self.assertEqual(report_mode(), "auto")
        with patch.dict(os.environ, {"CS_REPORT_MODE": "nonsense"}):
            self.assertEqual(report_mode(), "auto")
        with patch.dict(os.environ, {"CS_REPORT_MODE": "lean"}):
            # Removed after benchmarking: asking the model for a shorter report
            # cut output 23% on one question and raised it 22% on the next.
            self.assertEqual(report_mode(), "auto")

    def test_auto_reads_the_briefs_depth(self) -> None:
        with patch.dict(os.environ, {"CS_REPORT_MODE": "auto"}):
            self.assertEqual(resolve_mode(self._brief(depth="overview"), "discovery"), "raw")
            self.assertEqual(resolve_mode(self._brief(depth="detailed"), "discovery"), "llm")

    def test_advisory_keeps_its_model_call_in_every_mode(self) -> None:
        """A recommendation is not in any payload, so there is nothing to derive."""
        for mode in ("derived", "raw", "auto"):
            with patch.dict(os.environ, {"CS_REPORT_MODE": mode}):
                self.assertEqual(
                    resolve_mode(self._brief("solution_advisory", "detailed"), "solution_advisory"),
                    "llm",
                )

    def test_derived_discovery_report_passes_its_own_gate(self) -> None:
        report = derive_report(
            "discovery", self._brief(), [self._tool("catalogue_map", self.MAP)], []
        )
        DiscoveryReport.model_validate(report)
        self.assertEqual(
            [family["name"] for family in report["families"]],
            ["WiNtrip2 MCB & Isolator", "WiNtrip MCB & Isolator"],
        )
        self.assertIn("580", report["summary"])
        # An overview is gated on asking something back, never on ordering codes.
        self.assertTrue(report["follow_up_questions"])
        self.assertEqual(report["representative_skus"], [])
        self.assertFalse(_violations("discovery", report, "overview"))

    def test_a_listing_never_widens_what_a_search_found(self) -> None:
        """taxonomy_browse returns a node's whole contents, matched or not."""
        report = derive_report(
            "discovery",
            self._brief(),
            [self._tool("catalogue_map", self.MAP), self._tool("taxonomy_browse", self.BROWSE)],
            [],
        )
        names = [family["name"] for family in report["families"]]
        self.assertNotIn("Industrial Plugs and Sockets", names)
        # A category is not a family; only a leaf child is one.
        self.assertNotIn("MCB & Isolators", names)

    def test_a_listing_is_used_when_nothing_targeted_ran(self) -> None:
        report = derive_report(
            "discovery", self._brief(), [self._tool("taxonomy_browse", self.BROWSE)], []
        )
        self.assertEqual(
            [family["name"] for family in report["families"]],
            ["Industrial Plugs and Sockets"],
        )

    def test_every_specification_finding_carries_its_sku(self) -> None:
        """The gate's one universal rule, satisfied by construction rather than prompt."""
        evidence = [
            {
                "tool": "get_sku",
                "sku_code": "CSMBL1C10",
                "spec_id": "rated_current_a",
                "value_display": "10",
                "unit": "A",
                "source_of_truth": "code_grammar",
            },
            {"tool": "taxonomy_browse", "sku_code": None, "spec_id": None, "text": "a category"},
        ]
        report = derive_report(
            "spec_selection",
            self._brief("spec_selection", "detailed"),
            [self._tool("catalogue_map", self.MAP)],
            evidence,
        )
        SpecSelectionReport.model_validate(report)
        for finding in report["findings"]:
            if finding["kind"] == "specification":
                self.assertTrue(finding["source"]["sku_code"])
        self.assertFalse(_violations("spec_selection", report, "detailed"))

    def test_findings_are_capped(self) -> None:
        evidence = [
            {"tool": "get_sku", "sku_code": f"SKU{i}", "spec_id": "poles", "value_display": "4"}
            for i in range(60)
        ]
        with patch.dict(os.environ, {"CS_REPORT_MAX_FINDINGS": "5"}):
            report = derive_report(
                "discovery", self._brief(), [self._tool("catalogue_map", self.MAP)], evidence
            )
        self.assertEqual(len(report["findings"]), 5)

    def test_a_comparison_table_is_copied_not_retyped(self) -> None:
        payload = {
            "sku_codes": ["A", "B"],
            "axes": ["rated_current_a", "poles"],
            "rows": {
                "rated_current_a": {"A": "400", "B": "630"},
                "poles": {"A": "4", "B": "4"},
            },
            "peer_group_match": True,
        }
        report = derive_report(
            "comparison",
            self._brief("comparison", "detailed"),
            [self._tool("compare_skus", payload)],
            [],
        )
        ComparisonReport.model_validate(report)
        self.assertEqual(report["table"]["rows"], payload["rows"])
        self.assertTrue(report["peer_group_match"])
        self.assertFalse(_violations("comparison", report, "detailed"))

    def test_an_errored_call_contributes_nothing(self) -> None:
        bad = ToolMessage(
            content=json.dumps({"error": "no such family"}),
            tool_call_id="x",
            name="taxonomy_browse",
            status="error",
        )
        report = derive_report("discovery", self._brief(), [bad], [])
        self.assertEqual(report["status"], "no_result")
        self.assertEqual(report["families"], [])

    def test_raw_bundle_says_when_it_dropped_something(self) -> None:
        messages = [self._tool("get_sku", {"sku_code": f"S{i}", "facts": ["x" * 400]}) for i in range(6)]
        bundle = raw_bundle(messages, budget=1200)
        self.assertLess(len(bundle), 7)
        self.assertEqual(bundle[-1]["tool"], "__truncated__")
        # Newest first, because the last call is the one that answered.
        kept = [entry["result"]["sku_code"] for entry in bundle if entry["tool"] == "get_sku"]
        self.assertIn("S5", kept)
        self.assertNotIn("S0", kept)

    def test_raw_bundle_keeps_everything_inside_budget(self) -> None:
        messages = [self._tool("catalogue_map", self.MAP)]
        bundle = raw_bundle(messages, budget=100_000)
        self.assertEqual([entry["tool"] for entry in bundle], ["catalogue_map"])

    def test_the_slim_schema_never_shows_a_backfilled_field(self) -> None:
        """A field the model is not shown is one it cannot spend tokens on.

        Three of SourceRef's six fields were populated under 4% of the time
        across 503 measured references while being written as an explicit null
        in nearly all of them.
        """
        asked = _asked_for(SpecSelectionReport)
        for field in ("brochure_md", "pricelist_pdf", "pricelist_page", "product_page_url"):
            self.assertNotIn(field, asked)
        self.assertNotIn('"sources"', asked)
        self.assertIn("maxItems", asked)
        # The fields it still needs are still there.
        self.assertIn("sku_code", asked)
        self.assertIn("source_of_truth", asked)

    def test_turning_slimming_off_restores_the_whole_schema(self) -> None:
        with patch.dict(os.environ, {"CS_REPORT_SLIM": "0"}):
            asked = _asked_for(SpecSelectionReport)
        self.assertIn("brochure_md", asked)
        self.assertIn('"sources"', asked)

    def test_hiding_a_field_does_not_stop_the_model_accepting_it(self) -> None:
        """Pruning changes the asking, never the contract."""
        report = SpecSelectionReport.model_validate({
            "agent": "spec_selection",
            "status": "complete",
            "summary": "x",
            "sources": [{"sku_code": "A", "pricelist_page": 42}],
        })
        self.assertEqual(report.sources[0].pricelist_page, 42)


class BackfillTests(unittest.TestCase):
    """Restoring what the slim schema did not ask the model to write."""

    @staticmethod
    def _tool(name: str, payload: Any) -> ToolMessage:
        return ToolMessage(
            content=json.dumps(payload, default=str), tool_call_id=name, name=name
        )

    PRICES = {
        "prices": [
            {
                "sku_code": "CSCS400DM4CO",
                "observations": [
                    {"source_pdf": "LV-Pricelist-WEF-1st-June26.pdf", "source_page": 42}
                ],
            }
        ]
    }
    SEARCH = {
        "hits": [
            {"sku_code": "CSCS400DM4CO", "url": "https://example.invalid/changeover"}
        ]
    }

    def test_a_reference_gains_the_documents_its_payload_recorded(self) -> None:
        report = {
            "findings": [
                {
                    "statement": "400 A",
                    "kind": "specification",
                    "source": {"sku_code": "CSCS400DM4CO", "source_of_truth": "pricelist_table"},
                }
            ],
            "sources": [],
        }
        filled = backfill_report(
            report,
            [self._tool("get_price_detail", self.PRICES), self._tool("product_search", self.SEARCH)],
            [],
        )
        source = filled["findings"][0]["source"]
        self.assertEqual(source["pricelist_pdf"], "LV-Pricelist-WEF-1st-June26.pdf")
        self.assertEqual(source["pricelist_page"], 42)
        self.assertEqual(source["product_page_url"], "https://example.invalid/changeover")
        # What the model did write is left exactly as it wrote it.
        self.assertEqual(source["source_of_truth"], "pricelist_table")

    def test_a_reference_the_payloads_do_not_know_is_left_alone(self) -> None:
        report = {"findings": [{"statement": "x", "source": {"sku_code": "UNKNOWN"}}], "sources": []}
        filled = backfill_report(report, [self._tool("get_price_detail", self.PRICES)], [])
        self.assertIsNone(filled["findings"][0]["source"].get("pricelist_pdf"))

    def test_sources_indexes_what_the_report_references(self) -> None:
        """Provenance for the SKUs the report names, not a log of the retrieval.

        Rebuilding from every payload produced 20 entries where the model had
        chosen 4 — prompt weight the composer reads past for no gain.
        """
        report = {
            "findings": [
                {"statement": "x", "source": {"sku_code": "CSCS400DM4CO"}}
            ],
            "sources": [],
        }
        filled = backfill_report(
            report, [self._tool("get_price_detail", self.PRICES)], []
        )
        self.assertTrue(
            any(ref.get("pricelist_page") == 42 for ref in filled["sources"])
        )

    def test_a_report_that_references_nothing_cites_nothing(self) -> None:
        report = {"findings": [], "sources": []}
        filled = backfill_report(
            report, [self._tool("get_price_detail", self.PRICES)], []
        )
        self.assertEqual(filled["sources"], [])

    def test_a_pricelist_page_is_read_off_the_fact_that_carried_it(self) -> None:
        """The shape that actually appears when `get_price_detail` is never called.

        Provenance rides on individual facts inside a `get_sku` payload. Reading
        only the price-lookup shape lost the citation "LV-Pricelist-WEF-1st-June26
        .pdf, p. 42" on a run whose payloads plainly contained it.
        """
        payload = {
            "sku_code": "CSCS400DM4CO",
            "facts": [
                {
                    "spec_id": "price_inr",
                    "value_display": "₹60,910",
                    "source_of_truth": "pricelist_table",
                    "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
                    "source_page": 42,
                },
                {
                    "spec_id": "position_indication",
                    "source_of_truth": "brochure",
                    "source_pdf": None,
                    "source_page": None,
                },
            ],
        }
        report = {
            "findings": [
                {
                    "statement": "MRP ₹60,910",
                    "kind": "price",
                    "source": {"sku_code": "CSCS400DM4CO", "source_of_truth": "pricelist_table"},
                }
            ],
            "sources": [],
        }
        filled = backfill_report(report, [self._tool("get_sku", payload)], [])
        source = filled["findings"][0]["source"]
        self.assertEqual(source["pricelist_pdf"], "LV-Pricelist-WEF-1st-June26.pdf")
        self.assertEqual(source["pricelist_page"], 42)

    def test_a_sources_list_the_model_did_supply_is_kept(self) -> None:
        report = {"findings": [], "sources": [{"sku_code": "MINE"}]}
        filled = backfill_report(report, [self._tool("get_price_detail", self.PRICES)], [])
        self.assertEqual(filled["sources"], [{"sku_code": "MINE"}])

    def test_findings_are_trimmed_when_the_cap_is_ignored(self) -> None:
        report = {"findings": [{"statement": str(i)} for i in range(40)], "sources": []}
        with patch.dict(os.environ, {"CS_REPORT_FINDINGS_CAP": "6"}):
            filled = backfill_report(report, [], [])
        self.assertEqual(len(filled["findings"]), 6)


class CandidateProvenanceTests(unittest.TestCase):
    """A derived candidate may only claim the filters that returned it.

    A specialist runs several searches. Collecting every ordering code and every
    filter from the whole transcript and pairing them afterwards produced a
    report asserting that `CSCOS2P25A`, a 25 A two-pole device, matched
    `rated_current_a eq 400, poles eq 4` — a fabricated specification claim that
    the gate passes, because its shape is valid and only its meaning is wrong.
    """

    @staticmethod
    def _tool(name: str, payload: Any) -> ToolMessage:
        return ToolMessage(
            content=json.dumps(payload, default=str), tool_call_id=name, name=name
        )

    BRIEF = {
        "agent": "spec_selection",
        "objective": "Find a 400 A 4-pole changeover switch.",
        "depth": "detailed",
        "must_return": ["sku_code"],
        "parameters": {},
    }

    def _report(self) -> dict[str, Any]:
        empty = {"hits": [], "filters_applied": ["rated_current_a eq 400.0", "poles eq 4.0"]}
        wide = {"hits": [{"sku_code": "CSCOS2P25A", "family": "WiNtrip"}], "filters_applied": []}
        return derive_report("spec_selection", self.BRIEF, [
            self._tool("product_search", empty),
            self._tool("product_search", wide),
        ], [])

    def test_a_code_never_inherits_another_searchs_filters(self) -> None:
        report = self._report()
        why = {entry["sku_code"]: entry["why_it_fits"] for entry in report["candidates"]}
        self.assertIn("CSCOS2P25A", why)
        self.assertNotIn("400", why["CSCOS2P25A"])
        self.assertNotIn("poles", why["CSCOS2P25A"])

    def test_a_code_keeps_the_filters_that_did_return_it(self) -> None:
        hit = {
            "hits": [{"sku_code": "CSCS400DM4CO", "family": "New Changeover Switches"}],
            "filters_applied": ["rated_current_a eq 400.0", "poles eq 4.0"],
        }
        report = derive_report(
            "spec_selection", self.BRIEF, [self._tool("product_search", hit)], []
        )
        self.assertEqual(
            report["candidates"][0]["why_it_fits"],
            "Matches rated_current_a eq 400.0, poles eq 4.0",
        )

    def test_the_first_provenance_survives_a_later_unfiltered_sweep(self) -> None:
        filtered = {
            "hits": [{"sku_code": "CSCS400DM4CO"}],
            "filters_applied": ["rated_current_a eq 400.0"],
        }
        sweep = {"hits": [{"sku_code": "CSCS400DM4CO"}], "filters_applied": []}
        report = derive_report("spec_selection", self.BRIEF, [
            self._tool("product_search", filtered),
            self._tool("product_search", sweep),
        ], [])
        self.assertIn("400", report["candidates"][0]["why_it_fits"])

    def test_a_directly_fetched_code_claims_no_filter_at_all(self) -> None:
        report = derive_report("spec_selection", self.BRIEF, [
            self._tool("get_sku", {"sku_code": "CSCS400DM4CO", "family": "New Changeover"}),
        ], [])
        self.assertEqual(
            report["candidates"][0]["why_it_fits"], "Retrieved directly by ordering code"
        )


class EmptyCoreFallbackTests(unittest.TestCase):
    """When derivation finds nothing, writing the report with the model is cheaper.

    An empty derived report is not merely thin. The gate accepts it as a valid
    `no_result`, and the composer's sufficiency check then spends revision rounds
    chasing a gap no retry can close: one measured comparison ran 1,156s across
    three specialist rounds and 38 tool calls, and refused to answer.
    """

    @staticmethod
    def _tool(name: str, payload: Any) -> ToolMessage:
        return ToolMessage(
            content=json.dumps(payload, default=str), tool_call_id=name, name=name
        )

    def test_a_comparison_with_no_table_falls_back(self) -> None:
        self.assertTrue(
            needs_model_fallback("derived", "comparison", {"table": {"rows": {}}})
        )

    def test_a_comparison_with_a_table_does_not(self) -> None:
        report = {"table": {"rows": {"poles": {"A": "4"}}}}
        self.assertFalse(needs_model_fallback("derived", "comparison", report))

    def test_raw_never_falls_back(self) -> None:
        """Its payloads are the fallback: 426s against the model's 500s."""
        self.assertFalse(
            needs_model_fallback("raw", "comparison", {"table": {"rows": {}}})
        )

    def test_each_agent_is_judged_on_the_field_it_exists_to_produce(self) -> None:
        self.assertTrue(needs_model_fallback("derived", "discovery", {"families": []}))
        self.assertFalse(
            needs_model_fallback("derived", "discovery", {"families": [{"name": "x"}]})
        )
        self.assertTrue(
            needs_model_fallback("derived", "spec_selection", {"candidates": []})
        )

    def test_advisory_has_no_core_to_judge(self) -> None:
        """It never derives in the first place, so there is nothing to fall back from."""
        self.assertFalse(needs_model_fallback("derived", "solution_advisory", {}))

    def test_the_node_writes_with_the_model_when_the_core_is_empty(self) -> None:
        from cs_agent.subgraphs.agents.nodes import make_report_node

        called: dict[str, Any] = {}

        def _structured(node, messages, schema, **kw):
            called["hit"] = True
            return schema(agent="comparison", status="complete", summary="s")

        node = make_report_node("comparison")
        brief = {
            "agent": "comparison",
            "objective": "Compare two ranges.",
            "depth": "detailed",
            "parameters": {},
        }
        # A payload with no `compare_skus` in it: derivation yields no table.
        state = {
            "brief": brief,
            "agent_name": "comparison",
            "messages": [self._tool("product_search", {"hits": [{"sku_code": "A"}]})],
            "evidence": [],
        }
        with patch.dict(os.environ, {"CS_REPORT_MODE": "derived"}), patch(
            "cs_agent.subgraphs.agents.nodes.structured", side_effect=_structured
        ):
            node(state)
        self.assertTrue(called.get("hit"), "expected the model to write the report")


class StructuredToolCallTests(unittest.TestCase):
    """A schema request answered with a tool call has to be corrected as one.

    The failure is invisible from the content alone — a tool-calling reply
    carries no text, so the validator only ever sees an empty string.
    """

    class _Model:
        def __init__(self, name: str) -> None:
            self.name = name
            self.bound: list[object] | None = None

        def bind_tools(self, tools):
            clone = StructuredToolCallTests._Model(self.name)
            clone.bound = list(tools)
            return clone

    @staticmethod
    def _tool_reply(*names: str) -> AIMessage:
        return AIMessage(
            content="",
            tool_calls=[
                {"name": n, "args": {}, "id": f"call_{i}"}
                for i, n in enumerate(names)
            ],
        )

    @contextmanager
    def _run(self, replies: list[AIMessage]):
        """Drive `structured` through ``replies``, recording each request."""
        # `cs_agent.llm` re-exports the function under this name, so the
        # module itself has to be fetched by path.
        mod = importlib.import_module("cs_agent.llm.structured")

        seen: list[dict[str, Any]] = []
        queue = list(replies)

        def _generate(model, messages, *, label=None, tool_names=None, **kw):
            seen.append(
                {"model": model, "messages": list(messages), "tools": tool_names}
            )
            return queue.pop(0), False

        with patch.object(mod, "get_model", lambda node: self._Model(node)), patch.object(
            mod, "generate", _generate
        ):
            yield seen

    def _schema(self):
        from pydantic import BaseModel

        class Tiny(BaseModel):
            ok: bool

        return Tiny

    def test_a_tool_call_is_named_back_to_the_model(self) -> None:
        from cs_agent.llm.structured import structured

        schema = self._schema()
        replies = [self._tool_reply("product_search"), AIMessage(content='{"ok": true}')]
        with self._run(replies) as seen:
            result = structured(
                "agent", [HumanMessage(content="JSON Schema go")], schema,
                tools=[SimpleNamespace(name="product_search")],
            )
        self.assertTrue(result.ok)
        correction = seen[1]["messages"][-1]
        self.assertIn("product_search", correction.content)
        self.assertNotIn("EOF", correction.content)

    def test_the_empty_reply_is_kept_out_of_the_transcript(self) -> None:
        """An empty assistant turn teaches the model that empty is acceptable."""
        from cs_agent.llm.structured import structured

        schema = self._schema()
        replies = [self._tool_reply("get_sku"), AIMessage(content='{"ok": true}')]
        with self._run(replies) as seen:
            structured(
                "agent", [HumanMessage(content="JSON Schema go")], schema,
                tools=[SimpleNamespace(name="get_sku")],
            )
        added = seen[1]["messages"][len(seen[0]["messages"]):]
        self.assertEqual(len(added), 1, "only the correction should be appended")
        self.assertFalse(
            any(isinstance(m, AIMessage) and not m.content for m in added)
        )

    def test_one_tool_call_takes_the_tools_away(self) -> None:
        """Telling it not to does not work; removing the option does."""
        from cs_agent.llm.structured import structured

        schema = self._schema()
        replies = [self._tool_reply("product_search"), AIMessage(content='{"ok": true}')]
        with self._run(replies) as seen:
            structured(
                "agent", [HumanMessage(content="JSON Schema go")], schema,
                tools=[SimpleNamespace(name="product_search")],
            )
        self.assertIsNotNone(seen[0]["tools"], "tools bound on the first ask")
        self.assertIsNone(seen[1]["tools"], "unbound on the very next attempt")
        self.assertIsNone(seen[1]["model"].bound)

    def test_a_later_validation_failure_keeps_the_tools_off(self) -> None:
        """The retry that follows the unbinding must not re-bind them."""
        from cs_agent.llm.structured import structured

        schema = self._schema()
        replies = [
            self._tool_reply("product_search"),
            AIMessage(content="still not JSON"),
            AIMessage(content='{"ok": true}'),
        ]
        with self._run(replies) as seen:
            structured(
                "agent", [HumanMessage(content="JSON Schema go")], schema,
                tools=[SimpleNamespace(name="product_search")],
            )
        self.assertEqual(
            [s["tools"] is None for s in seen], [False, True, True]
        )

    def test_unparseable_text_still_gets_the_validation_error(self) -> None:
        from cs_agent.llm.structured import structured

        schema = self._schema()
        replies = [AIMessage(content="sorry, no"), AIMessage(content='{"ok": true}')]
        with self._run(replies) as seen:
            structured("agent", [HumanMessage(content="JSON Schema go")], schema)
        added = seen[1]["messages"][len(seen[0]["messages"]):]
        self.assertEqual([type(m) for m in added], [AIMessage, HumanMessage])
        self.assertIn("Invalid output", added[1].content)

    def test_it_still_gives_up_when_nothing_works(self) -> None:
        from cs_agent.llm.structured import StructuredOutputError, structured

        schema = self._schema()
        replies = [self._tool_reply("get_sku") for _ in range(3)]
        with self._run(replies):
            with self.assertRaises(StructuredOutputError):
                structured(
                    "agent", [HumanMessage(content="JSON Schema go")], schema,
                    tools=[SimpleNamespace(name="get_sku")],
                )


class BatchedScopeTests(unittest.TestCase):
    """The four things the multi-family widening got wrong on its first pass."""

    def _specs_payload(self) -> dict[str, Any]:
        return {
            "specs": [
                {
                    "family": "ACB – WiNmaster 2",
                    "spec_id": "rated_current_a",
                    "spec_label": "Rated current",
                    "unit": "A",
                    "value_kind": "scalar",
                    "is_canonical_spec": 1,
                    "sku_count": 101,
                    "composite_count": 0,
                    "observed_min": 630.0,
                    "observed_max": 2500.0,
                },
                {
                    "family": "ACB – WiNmaster 3",
                    "spec_id": "rated_current_a",
                    "spec_label": "Rated current",
                    "unit": "A",
                    "value_kind": "scalar",
                    "is_canonical_spec": 1,
                    "sku_count": 157,
                    "composite_count": 0,
                    "observed_min": 630.0,
                    "observed_max": 4000.0,
                },
            ],
            "scope": {"path": None, "family": ["ACB – WiNmaster 2", "ACB – WiNmaster 3"]},
        }

    def test_the_envelope_is_indexed_row_by_row(self) -> None:
        """The rows are evidence; the envelope around them is not."""
        from cs_agent.graph.nodes.record_evidence import _extract

        records = _extract(self._specs_payload(), "list_canonical_specs")
        counts = [r for r in records if r.get("source_of_truth") == "catalogue_index"]
        self.assertTrue(counts, "per-spec counts and bounds must survive the envelope")
        self.assertTrue(
            any(r.get("value_num") == 4000.0 for r in counts),
            "WiNmaster 3's observed_max is quotable evidence",
        )
        self.assertTrue(any(r.get("value_kind") == "name" for r in records))
        # The whole payload as one blob is what the envelope caused before.
        self.assertLess(max(len(r.get("text") or "") for r in records), 1000)

    def test_spec_rows_are_not_filed_as_sku_facts(self) -> None:
        from cs_agent.graph.nodes.record_evidence import _extract

        records = _extract(self._specs_payload(), "list_canonical_specs")
        self.assertFalse(
            [r for r in records if r.get("spec_id") and r.get("source_of_truth") is None],
            "a spec definition is not a fact about a SKU",
        )

    def test_the_payload_carries_the_rows_and_the_scope_only(self) -> None:
        """No second copy of the rows: a rollup alongside them doubled the payload."""
        from cs_agent.backends.spec_envelope import group_specs

        payload = group_specs(
            self._specs_payload()["specs"],
            groups=["ACB – WiNmaster 2", "ACB – WiNmaster 3"],
            group_by="family", path=None, family=["A", "B"],
        )
        self.assertEqual({"specs", "scope"}, set(payload))
        self.assertNotIn("by_spec_id", payload)

    def test_a_level_group_reports_the_group_path_not_a_members(self) -> None:
        from cs_agent.backends.grouped_search import group_path

        hit = {
            "family": "MCCB – Winbreak1",
            "path": [
                "Low Voltage Products and Solutions",
                "Circuit Breakers",
                "Moulded Case Circuit Breakers",
                "MCCB – Winbreak1",
            ],
        }
        self.assertEqual(
            ["Low Voltage Products and Solutions", "Circuit Breakers"],
            group_path(hit, "product_group"),
        )
        self.assertEqual(
            ["Low Voltage Products and Solutions"], group_path(hit, "division")
        )
        # A family is a leaf, so its own path is the group's path.
        self.assertEqual(hit["path"], group_path(hit, "family"))

    def test_grouped_hits_reach_the_derived_report(self) -> None:
        from cs_agent.subgraphs.agents.report_modes import _candidates, _skus

        grouped = {
            "group_by": "family",
            "groups": [
                {
                    "family": "ACB – WiNmaster 3",
                    "path": [],
                    "total_in_scope": 157,
                    "matched": 156,
                    "spec_present": True,
                    "sample_hits": [{"sku_code": "WX306L3P1MDOA", "family": "ACB – WiNmaster 3"}],
                },
                {
                    "family": "2 & 4 Pole Contactors",
                    "path": [],
                    "total_in_scope": 63,
                    "matched": 0,
                    "spec_present": False,
                    "sample_hits": [],
                },
            ],
            "filters_applied": ["rated_current_a gte 400.0"],
        }
        items = [("product_search", grouped)]
        self.assertEqual(["WX306L3P1MDOA"], _skus(items))
        candidate = _candidates(items)[0]
        self.assertEqual("WX306L3P1MDOA", candidate["sku_code"])
        self.assertIn("rated_current_a gte 400.0", candidate["why_it_fits"])

    def test_every_agent_holding_the_tools_is_told_to_batch(self) -> None:
        """The syntax alone changed nothing; the instruction is what does."""
        from cs_agent.tools.registry import AGENT_TOOL_NAMES, SHARED_TOOL_NAMES

        common = Path("cs_agent/prompts/agent_common.md").read_text(encoding="utf-8")
        self.assertIn("ONE call", common)
        self.assertIn("group_by", common)
        for agent, names in AGENT_TOOL_NAMES.items():
            held = set(names) | set(SHARED_TOOL_NAMES)
            if not held & {"product_search", "list_canonical_specs"}:
                continue
            raw = Path(f"cs_agent/prompts/agents/{agent}.md").read_text(encoding="utf-8")
            # These files are hard-wrapped, so a phrase can straddle a newline.
            text = " ".join(raw.lower().split())
            self.assertTrue(
                any(
                    phrase in text
                    for phrase in ("one call", "one list_canonical_specs", "together")
                ),
                f"{agent} holds the widened tools but is not told to batch",
            )


class CompactFactTests(unittest.TestCase):
    """Dropping a null must lose no meaning, and no consumer may KeyError on it."""

    ROW = {
        "sku_code": "CSCS400DM4CO",
        "product_id": 102363,
        "spec_id": "rated_current_a",
        "spec_label": "Rated current",
        "unit": None,
        "value_num": None,
        "value_min": None,
        "value_max": None,
        "value_display": "400 A",
        "value_kind": "text",
        "source_of_truth": "pricelist_table",
        "source_pdf": None,
        "source_page": None,
    }

    def test_nulls_go_and_values_stay(self) -> None:
        from cs_agent.backends.spec_envelope import compact_fact

        out = compact_fact(dict(self.ROW))
        self.assertNotIn("unit", out)
        self.assertNotIn("value_num", out)
        self.assertEqual("400 A", out["value_display"])
        self.assertEqual("pricelist_table", out["source_of_truth"])
        # spec_label is not recoverable from spec_id on 41% of the catalogue
        # (`1_no_1_nc` is published as `1 NO + 1 NC`), so it is never dropped.
        self.assertEqual("Rated current", out["spec_label"])

    def test_a_falsy_value_is_not_a_missing_one(self) -> None:
        """`is_canonical_spec: 0` and `sku_count: 0` are answers, not absences."""
        from cs_agent.backends.spec_envelope import compact_fact

        out = compact_fact({"spec_id": "x", "is_canonical_spec": 0, "sku_count": 0,
                            "value_num": 0.0, "unit": "", "gone": None})
        self.assertEqual(0, out["is_canonical_spec"])
        self.assertEqual(0, out["sku_count"])
        self.assertEqual(0.0, out["value_num"])
        self.assertEqual("", out["unit"])
        self.assertNotIn("gone", out)

    def test_nested_rows_shed_what_the_parent_hit_already_says(self) -> None:
        from cs_agent.backends.spec_envelope import NESTED_REDUNDANT, compact_fact

        out = compact_fact(dict(self.ROW), drop=NESTED_REDUNDANT)
        self.assertNotIn("sku_code", out)
        self.assertNotIn("product_id", out)

    def test_evidence_survives_a_compacted_row(self) -> None:
        """A compacted row must still produce a fully-keyed Evidence record."""
        from cs_agent.backends.spec_envelope import NESTED_REDUNDANT, compact_fact
        from cs_agent.graph.nodes.record_evidence import _empty, _fact_record

        compact = compact_fact(dict(self.ROW), drop=NESTED_REDUNDANT)
        record = _fact_record("product_search", compact, "CSCS400DM4CO")
        self.assertEqual(set(_empty("product_search")), set(record))
        self.assertEqual("CSCS400DM4CO", record["sku_code"])
        self.assertEqual("400 A", record["value_display"])
        self.assertIsNone(record["unit"])

    def test_a_price_citation_survives_compaction(self) -> None:
        """The fix for this morning's citation regression must not be undone."""
        from cs_agent.backends.spec_envelope import NESTED_REDUNDANT, compact_fact
        from cs_agent.subgraphs.agents.report_modes import _reference_index

        priced = {**self.ROW, "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
                  "source_page": 42}
        hit = {"sku_code": "CSCS400DM4CO",
               "specs": [compact_fact(priced, drop=NESTED_REDUNDANT)]}
        index = _reference_index([("product_search", {"hits": [hit]})])
        self.assertEqual(42, index["CSCS400DM4CO"]["pricelist_page"])
        self.assertEqual(
            "LV-Pricelist-WEF-1st-June26.pdf",
            index["CSCS400DM4CO"]["pricelist_pdf"],
        )


class SharedScopeTests(unittest.TestCase):
    """Several families asked about at once means: what do they have in common?"""

    def setUp(self) -> None:
        self.backend = FixturesBackend()

    def test_only_specs_every_group_publishes_come_back(self) -> None:
        from cs_agent.backends.spec_envelope import group_specs

        rows = [
            {"family": "A", "spec_id": "poles", "sku_count": 2, "observed_max": 4},
            {"family": "B", "spec_id": "poles", "sku_count": 3, "observed_max": 3},
            {"family": "A", "spec_id": "only_a", "sku_count": 1},
        ]
        out = group_specs(rows, groups=["A", "B"], group_by="family",
                          path=None, family=["A", "B"])
        self.assertEqual(["poles"], [row["spec_id"] for row in out["specs"]])
        self.assertEqual({"only_a": ["A"]}, out["not_shared"]["spec_ids"])

    def test_per_group_bounds_are_never_merged(self) -> None:
        """WiNmaster 3 reaching 4000 A where 2 stops at 2500 A is the answer."""
        from cs_agent.backends.spec_envelope import group_specs

        rows = [
            {"family": "W2", "spec_id": "rated_current_a", "sku_count": 101,
             "observed_min": 630.0, "observed_max": 2500.0},
            {"family": "W3", "spec_id": "rated_current_a", "sku_count": 157,
             "observed_min": 630.0, "observed_max": 4000.0},
        ]
        out = group_specs(rows, groups=["W2", "W3"], group_by="family",
                          path=None, family=["W2", "W3"])
        by_group = out["specs"][0]["by_group"]
        self.assertEqual(2500.0, by_group["W2"]["observed_max"])
        self.assertEqual(4000.0, by_group["W3"]["observed_max"])

    def test_a_group_holding_nothing_still_counts_against_the_intersection(self) -> None:
        """Otherwise one family out of three reads as shared by all three."""
        from cs_agent.backends.spec_envelope import group_specs

        rows = [{"family": "A", "spec_id": "poles", "sku_count": 1}]
        out = group_specs(rows, groups=["A", "B", "C"], group_by="family",
                          path=None, family=["A", "B", "C"])
        self.assertEqual([], out["specs"])
        self.assertEqual({"poles": ["A"]}, out["not_shared"]["spec_ids"])

    def test_one_family_shares_everything_with_itself(self) -> None:
        result = self.backend.list_canonical_specs(family="WIN2-125")
        self.assertTrue(result["specs"])
        self.assertNotIn("not_shared", result)
        self.assertEqual(["WIN2-125"], result["scope"]["groups"])

    def test_product_search_attaches_only_shared_specs(self) -> None:
        kept, dropped = self.backend._shared_return_specs(
            {"family": ["WIN2-125", "DP09"]}, ["poles", "rated_current_a"]
        )
        self.assertNotIn("poles", kept, "DP09 does not publish poles")
        self.assertEqual(["WIN2-125"], dropped["poles"])

    def test_a_single_group_scope_attaches_everything_asked_for(self) -> None:
        """The intersection must not narrow an ordinary one-family search."""
        kept, dropped = self.backend._shared_return_specs(
            {"family": "WIN2-125"}, ["poles", "rated_current_a"]
        )
        self.assertEqual(["poles", "rated_current_a"], kept)
        self.assertEqual({}, dropped)

    def test_the_excluded_ids_are_always_named(self) -> None:
        """Silence would read as 'the catalogue does not publish this'."""
        result = self.backend.list_canonical_specs(family=["WIN2-125", "DP09"])
        self.assertIn("not_shared", result)
        self.assertIn("spec_ids", result["not_shared"])
        self.assertTrue(result["not_shared"]["note"])
        for holders in result["not_shared"]["spec_ids"].values():
            self.assertTrue(holders, "each excluded id names who does publish it")


class SkuIdentityTests(unittest.TestCase):
    """The ordering code is the identity. `product_id` must not stand in for it.

    Several distinct ordering codes share one `product_id` in the build source
    -- `CE20113` and `CE20113NR` do, with different content, chunk counts and
    facts. Keying anything on `product_id` collapses them: 544 codes were lost
    that way, 261 of which had previously resolved, and `mv_fact` handed one
    code's specifications to its sibling.
    """

    def test_no_tool_payload_leaks_product_id(self) -> None:
        """It identifies nothing the caller can act on, and invites grouping."""
        import inspect
        from cs_agent.backends import sqlite as backend

        source = inspect.getsource(backend)
        emitted = [
            line.strip()
            for line in source.splitlines()
            if '"product_id"' in line and not line.strip().startswith("#")
        ]
        self.assertEqual([], emitted, "product_id must not reach a tool payload")

    def test_the_views_key_on_the_ordering_code(self) -> None:
        sql = Path("cs_agent/db/views.sql").read_text(encoding="utf-8")
        self.assertIn("SELECT DISTINCT ON (product->>'sku_code')", sql)
        self.assertNotIn("SELECT DISTINCT ON (product_id)", sql)
        # A unique index on product_id is what forced the collapse.
        self.assertNotIn("CREATE UNIQUE INDEX mv_sku_product_id_idx", sql)
        self.assertIn("CREATE UNIQUE INDEX mv_sku_sku_code_idx", sql)
        # Facts belong to the code's own chunk.
        self.assertIn("pc.product->>'sku_code' = s.sku_code", sql)
        self.assertIn("x.product->>'sku_code' = s.sku_code", sql)
        # Counting products means counting ordering codes.
        self.assertIn("count(DISTINCT sku_code) AS sku_count", sql)

    def test_the_build_keys_on_the_ordering_code(self) -> None:
        build = Path("scripts/build_sqlite.py").read_text(encoding="utf-8")
        self.assertIn("sku_by_code", build)
        self.assertIn("facts_by_code", build)
        self.assertNotIn("sku_by_product", build)
        self.assertNotIn("facts_by_product", build)
        self.assertIn('cur.execute("SELECT * FROM in_use.mv_sku ORDER BY sku_code")', build)

    def test_a_hit_and_a_sku_carry_no_product_id(self) -> None:
        from cs_agent.tools.impl import get_sku, product_search

        backend = FixturesBackend()
        with patch("cs_agent.tools.impl.backend", return_value=backend):
            hits = product_search(family=None, limit=3).get("hits") or []
            self.assertTrue(hits)
            for hit in hits:
                self.assertNotIn("product_id", hit)
                self.assertTrue(hit.get("sku_code"))
                for spec in hit.get("specs") or []:
                    self.assertNotIn("product_id", spec)
            sku = get_sku(sku_code=hits[0]["sku_code"], include=["facts"])
            self.assertNotIn("product_id", sku)
