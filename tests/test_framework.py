import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cs_agent.backends import FixturesBackend, PostgresBackend
from cs_agent.graph import build_graph
from cs_agent.graph.state import Evidence
from cs_agent.observability import AgentCallbackHandler, TraceLogger
from cs_agent.tools.impl import backend, reset_backend
from cs_agent.tools.registry import TOOLS_BY_NAME
from cs_agent.validation.numeric_fidelity import validate_numeric_fidelity


class FixturesBackendTests(unittest.TestCase):
    def setUp(self):
        self.catalog = FixturesBackend()

    def test_taxonomy_and_conditional_search(self):
        root = self.catalog.taxonomy_browse(None, depth=2)
        self.assertGreaterEqual(len(root["children"]), 2)
        rejected = self.catalog.product_search(
            category_path="protection/mccb",
            filters=[
                {
                    "canonical_fact_id": "icu_ka",
                    "op": "gte",
                    "value": 36,
                    "conditions": {},
                }
            ],
        )
        self.assertIn("requires conditions", rejected["error"])
        accepted = self.catalog.product_search(
            category_path="protection/mccb",
            filters=[
                {
                    "canonical_fact_id": "icu_ka",
                    "op": "gte",
                    "value": 36,
                    "conditions": {"voltage_v": 415},
                }
            ],
        )
        self.assertEqual(len(accepted), 3)

    def test_document_search_and_analytics(self):
        self.assertTrue(
            self.catalog.search_documents(
                query="electronic trip", category_path="protection/mccb"
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
                "category_path": "switching/contactor",
                "filters": [
                    {
                        "canonical_fact_id": "motor_power_kw",
                        "op": "gte",
                        "value": 7.5,
                        "conditions": {"voltage_v": 415},
                    }
                ],
            }
        )
        self.assertEqual(len(result), 2)

    def test_list_canonical_facts(self):
        facts = self.catalog.list_canonical_facts("protection/mccb")
        icu = next(fact for fact in facts if fact["id"] == "icu_ka")
        self.assertEqual(icu["condition_keys"], ["voltage_v"])


class BoundaryTests(unittest.TestCase):
    def test_postgres_is_explicitly_pending(self):
        with self.assertRaisesRegex(NotImplementedError, "SCHEMA_PENDING"):
            PostgresBackend().list_canonical_facts(None)

    def test_environment_selects_postgres(self):
        reset_backend()
        with patch.dict(os.environ, {"CS_BACKEND": "postgres"}):
            self.assertIsInstance(backend(), PostgresBackend)
        reset_backend()


class GraphAndValidationTests(unittest.TestCase):
    def test_graph_builds_without_live_llm(self):
        graph = build_graph()
        self.assertIn("planner", graph.get_graph().nodes)
        self.assertIn("validator", graph.get_graph().nodes)

    def test_numeric_conditions_must_be_in_sentence(self):
        evidence: list[Evidence] = [
            {
                "tool": "product_search",
                "family_id": "EXAMPLE-1",
                "canonical_fact_id": "breaking_capacity",
                "value_num": 36,
                "value_text": None,
                "unit": "kA",
                "conditions": {"voltage_v": 415},
                "doc": None,
                "page": None,
            }
        ]
        valid = validate_numeric_fidelity(
            "EXAMPLE-1 provides 36 kA at 415 V.", evidence
        )
        invalid = validate_numeric_fidelity("It provides 36 kA.", evidence)
        self.assertTrue(valid.passed)
        self.assertFalse(invalid.passed)

    def test_decimal_claim_is_not_split_as_two_sentences(self):
        evidence: list[Evidence] = [
            {
                "tool": "get_product",
                "family_id": "EXAMPLE-2",
                "canonical_fact_id": "power",
                "value_num": 7.5,
                "value_text": None,
                "unit": "kW",
                "conditions": {},
                "doc": None,
                "page": None,
            }
        ]
        self.assertTrue(
            validate_numeric_fidelity(
                "EXAMPLE-2 is rated at 7.5 kW.", evidence
            ).passed
        )


class ObservabilityTests(unittest.TestCase):
    def test_tool_events_are_written_to_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            trace = TraceLogger(file_path=path, print_to_screen=False)
            callback = AgentCallbackHandler(trace)
            TOOLS_BY_NAME["taxonomy_browse"].invoke(
                {"node_id": None, "depth": 1},
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
