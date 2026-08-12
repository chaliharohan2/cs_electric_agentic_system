import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import ToolMessage

from cs_agent.backends import FixturesBackend, PostgresBackend
from cs_agent.embeddings.factory import embed
from cs_agent.graph import build_graph
from cs_agent.graph.nodes.record_evidence import _extract, record_evidence
from cs_agent.graph.state import Evidence
from cs_agent.observability import AgentCallbackHandler, TraceLogger
from cs_agent.subgraphs.analytics.build import _after_execute
from cs_agent.tools.impl import backend, reset_backend
from cs_agent.tools.registry import TOOLS_BY_NAME
from cs_agent.validation.numeric_fidelity import validate_numeric_fidelity


class FixturesBackendTests(unittest.TestCase):
    def setUp(self):
        self.catalog = FixturesBackend()

    def test_taxonomy_and_conditional_search(self):
        root = self.catalog.taxonomy_browse()
        self.assertGreaterEqual(len(root["categories"]), 2)
        accepted = self.catalog.product_search(
            category="protection/mccb",
            filters=[
                {
                    "spec_id": "icu_ka",
                    "op": "gte",
                    "value": 36,
                }
            ],
        )
        self.assertGreaterEqual(len(accepted), 3)

    def test_document_search_and_analytics(self):
        self.assertTrue(
            self.catalog.search_documents(
                query="electronic trip", category="protection/mccb"
            )
        )
        result = self.catalog.execute_sql(
            "SELECT category, COUNT(*) AS total FROM families GROUP BY category"
        )
        self.assertEqual(len(result["rows"]), 2)
        self.assertIn("error", self.catalog.execute_sql("DELETE FROM families"))

    def test_structured_product_search_tool(self):
        result = TOOLS_BY_NAME["product_search"].invoke(
            {
                "category": "switching/contactor",
                "filters": [
                    {
                        "spec_id": "motor_power_kw",
                        "op": "gte",
                        "value": 7.5,
                    }
                ],
            }
        )
        self.assertEqual(len(result), 4)

    def test_list_canonical_specs_and_compare(self):
        specs = self.catalog.list_canonical_specs("protection/mccb")
        icu = next(fact for fact in specs if fact["spec_id"] == "icu_ka")
        self.assertEqual(icu["value_kind"], "scalar")
        comparison = self.catalog.compare_skus(
            ["WIN2-125-3P-63", "WIN2-250-4P-250"], ["rated_current_a"]
        )
        self.assertEqual(comparison["rows"][0]["values"]["WIN2-125-3P-63"], "125")


class BoundaryTests(unittest.TestCase):
    def test_postgres_requires_database_url(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
                PostgresBackend()

    def test_environment_selects_postgres(self):
        reset_backend()
        with patch.dict(
            os.environ,
            {"CS_BACKEND": "postgres", "DATABASE_URL": "postgresql://example"},
        ):
            self.assertIsInstance(backend(), PostgresBackend)
        reset_backend()


class GraphAndValidationTests(unittest.TestCase):
    def test_graph_builds_without_live_llm(self):
        graph = build_graph()
        self.assertIn("planner", graph.get_graph().nodes)
        self.assertIn("validator", graph.get_graph().nodes)
        self.assertEqual(
            set(TOOLS_BY_NAME),
            {
                "taxonomy_browse",
                "list_canonical_specs",
                "product_search",
                "get_sku",
                "compare_skus",
                "search_documents",
                "analytics_query",
            },
        )

    def test_analytics_error_retry_is_bounded(self):
        self.assertEqual(
            _after_execute({"result": {"error": "bad SQL"}, "retries": 1}),
            "write_sql",
        )
        self.assertEqual(
            _after_execute({"result": {"error": "bad SQL"}, "retries": 3}),
            "shape",
        )
        self.assertEqual(
            _after_execute({"result": {"rows": []}, "retries": 0}),
            "shape",
        )

    def test_numeric_range_and_ordering_code(self):
        evidence: list[Evidence] = [
            {
                "tool": "product_search",
                "sku_code": "WX306L3P1MDOA(S)",
                "spec_id": "rated_current_a",
                "value_num": None,
                "value_min": 630,
                "value_max": 800,
                "value_display": "630-800",
                "value_kind": "range",
                "unit": "A",
                "source_of_truth": "pricelist_table",
                "text": None,
            }
        ]
        valid = validate_numeric_fidelity(
            "WX306L3P1MDOA(S) covers 630-800 A.", evidence
        )
        invalid = validate_numeric_fidelity("It provides 900 A.", evidence)
        self.assertTrue(valid.passed)
        self.assertFalse(invalid.passed)

    def test_decimal_claim_is_not_split_as_two_sentences(self):
        evidence: list[Evidence] = [
            {
                "tool": "get_sku",
                "sku_code": "EXAMPLE-2",
                "spec_id": "power",
                "value_num": 7.5,
                "value_min": None,
                "value_max": None,
                "value_display": "7.5",
                "value_kind": "scalar",
                "unit": "kW",
                "source_of_truth": "fixture",
                "text": None,
            }
        ]
        self.assertTrue(
            validate_numeric_fidelity(
                "EXAMPLE-2 is rated at 7.5 kW.", evidence
            ).passed
        )

    def test_evidence_parser_reads_compare_facts(self):
        payload = FixturesBackend().compare_skus(
            ["WIN2-125-3P-63", "WIN2-250-4P-250"], ["rated_current_a"]
        )
        records = _extract(payload, "compare_skus")
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record["spec_id"] == "rated_current_a" for record in records))

    def test_evidence_node_counts_completed_tool_calls(self):
        update = record_evidence(
            {
                "messages": [
                    ToolMessage(
                        content="[]",
                        name="product_search",
                        tool_call_id="call-1",
                    )
                ],
                "tool_calls_made": 4,
            }
        )
        self.assertEqual(update["tool_calls_made"], 5)

    def test_embedding_dimension_mismatch_fails_before_model_load(self):
        with self.assertRaisesRegex(ValueError, "expects 768"):
            embed("breaker", expected_dimension=768)


class ObservabilityTests(unittest.TestCase):
    def test_tool_events_are_written_to_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            trace = TraceLogger(file_path=path, print_to_screen=False)
            callback = AgentCallbackHandler(trace)
            TOOLS_BY_NAME["taxonomy_browse"].invoke(
                {"category": None, "family": None},
                config={"callbacks": [callback]},
            )
            trace.close()

            records = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            events = [record["event"] for record in records]
            self.assertIn("tool.start", events)
            self.assertIn("tool.end", events)
            self.assertTrue(all(record["run_id"] == trace.run_id for record in records))

    def test_traced_graph_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = TraceLogger(
                file_path=Path(directory) / "trace.jsonl",
                print_to_screen=False,
            )
            graph = build_graph(trace=trace)
            self.assertIn("tools", graph.get_graph().nodes)
            trace.close()


if __name__ == "__main__":
    unittest.main()
