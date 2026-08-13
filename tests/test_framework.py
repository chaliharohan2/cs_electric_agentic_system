"""Offline v2 framework tests. No live model, database, or embedding calls."""

from __future__ import annotations

import importlib
import os
import unittest
from pathlib import Path
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
    SourceRef,
    SpecSelectionReport,
)
from cs_agent.embeddings.factory import resolve_embedding
from cs_agent.graph.build import (
    _after_composer,
    _after_gate,
    _after_planner,
    build_graph,
)
from cs_agent.graph.nodes.gate import gate
from cs_agent.graph.state import merge_reports
from cs_agent.llm.factory import clear_model_cache, resolve_endpoint
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
                "dispatch": [{"agent": "discovery"}],
                "reports": {"discovery": report.model_dump()},
                "gate_retries": 0,
            }
        )
        self.assertFalse(result["gate_result"]["ok"])
        self.assertEqual(1, result["gate_retries"])

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
                "dispatch": [{"agent": "compliance"}],
                "reports": {"compliance": report.model_dump()},
                "gate_retries": 0,
            }
        )
        self.assertFalse(result["gate_result"]["ok"])

    def test_report_reducer_is_parallel_safe_and_resettable(self) -> None:
        merged = merge_reports({"discovery": {"status": "complete"}}, {
            "comparison": {"status": "partial"}
        })
        self.assertEqual({"discovery", "comparison"}, set(merged))
        self.assertEqual({}, merge_reports(merged, {"__reset__": {}}))


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

    def test_planner_fans_out_send_objects(self) -> None:
        state = {
            "plan": {"needs_clarification": False},
            "dispatch": [
                AgentBrief(
                    agent="discovery",
                    objective="map MCCBs",
                    allowance=10,
                ).model_dump(),
                AgentBrief(
                    agent="spec_selection",
                    objective="filter MCCBs",
                    allowance=10,
                ).model_dump(),
            ],
            "standalone_question": "show MCCBs",
        }
        sends = _after_planner(state)
        self.assertEqual(2, len(sends))
        self.assertTrue(all(send.node == "specialist" for send in sends))

    def test_gate_retry_is_targeted(self) -> None:
        state = {
            "gate_result": {
                "ok": False,
                "failures": [
                    {"agent": "discovery", "violations": ["needs SKU"]}
                ],
            },
            "gate_retries": 1,
            "dispatch": [
                AgentBrief(
                    agent="discovery", objective="map", allowance=10
                ).model_dump()
            ],
            "standalone_question": "map",
            "tool_calls_made": 0,
            "turn_tool_calls_start": 0,
        }
        sends = _after_gate(state)
        self.assertEqual(1, len(sends))
        self.assertIn("needs SKU", sends[0].arg["brief"]["revision_note"])

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
                    agent="compliance", objective="check IEC", allowance=10
                ).model_dump()
            ],
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

    def test_vector_tests_are_not_in_default_make_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        test_target = makefile.split("test:", 1)[1].split("\ntest-vector:", 1)[0]
        self.assertIn("tests.test_framework", test_target)
        self.assertNotIn("test_vector_retrieval", test_target)


if __name__ == "__main__":
    unittest.main()
