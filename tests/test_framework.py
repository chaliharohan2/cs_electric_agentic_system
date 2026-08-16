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

from langchain_core.messages import HumanMessage

from cs_agent.backends.fixtures import FixturesBackend
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
                    {"agent": "discovery", "stage": 1},
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
                    agent="discovery", objective="map MCCBs", stage=1
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
