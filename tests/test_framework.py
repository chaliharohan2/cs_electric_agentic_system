"""Offline v2 framework tests. No live model, database, or embedding calls."""

from __future__ import annotations

import importlib
import json
import os
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from cs_agent.backends.fixtures import FixturesBackend
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
from cs_agent.embeddings.factory import resolve_embedding
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
)
from cs_agent.run import _initial_state
from cs_agent.subgraphs.agents import build_specialist_graph
from cs_agent.tools.registry import TOOLS_BY_NAME, tools_for_agent
from cs_agent.tools.schemas import ProductSearchArgs, SearchDocumentsArgs

ROOT = Path(__file__).parents[1]


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
        with patch(
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
        node = make_tool_node([])
        with patch(
            "cs_agent.subgraphs.agents.tool_node.ToolNode",
            return_value=SimpleNamespace(invoke=_fake),
        ):
            node = make_tool_node([])
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
            result = make_tool_node([])(
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

        result = impl.list_canonical_specs(family="Switch Sockets")
        self.assertIsInstance(result, dict)
        self.assertEqual("Switch Sockets", result["family_not_found"])
        self.assertIn("taxonomy_browse", result["hint"])

    def test_a_family_that_exists_returns_plain_rows(self) -> None:
        from cs_agent.tools import impl

        family = impl._known_families()[0]
        self.assertIsInstance(impl.list_canonical_specs(family=family), list)

    def test_the_final_answer_streams(self) -> None:
        """~35s of silence at the end of every run, at 12 tok/s."""
        # By module path: `cs_agent.graph.nodes.composer` also names a function
        # re-exported from the package.
        composer_module = importlib.import_module("cs_agent.graph.nodes.composer")

        class _Model:
            def stream(self, messages):
                for piece in ("Three ", "ACB ", "families."):
                    yield SimpleNamespace(content=piece)

        with patch.object(composer_module, "get_model", return_value=_Model()):
            text, streamed = composer_module._stream_answer([])
        self.assertEqual("Three ACB families.", text)
        self.assertFalse(streamed)  # no active trace, so nothing was printed


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
        fake = SimpleNamespace(list_canonical_specs=lambda **kw: rows)
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

        fake = SimpleNamespace(list_canonical_specs=list_specs)
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
        self.assertTrue(any(row["spec_id"] == "rated_current_a" for row in specs))

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


if __name__ == "__main__":
    unittest.main()
