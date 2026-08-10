import os
import unittest
from unittest.mock import patch

from cs_agent.backends import FixturesBackend, PostgresBackend
from cs_agent.graph import build_graph
from cs_agent.graph.state import Evidence
from cs_agent.tools.impl import backend, reset_backend
from cs_agent.validation.numeric_fidelity import validate_numeric_fidelity


class FixturesBackendTests(unittest.TestCase):
    def setUp(self):
        self.catalog = FixturesBackend()

    def test_categories_and_conditional_search(self):
        categories = self.catalog.list_categories()
        self.assertEqual(len(categories), 2)
        rejected = self.catalog.product_search(
            "protection/mccb",
            [
                {
                    "canonical_fact_id": "icu_ka",
                    "operator": "gte",
                    "value_num": 36,
                    "conditions": {},
                }
            ],
        )
        self.assertIn("requires conditions", rejected["error"])
        accepted = self.catalog.product_search(
            "protection/mccb",
            [
                {
                    "canonical_fact_id": "icu_ka",
                    "operator": "gte",
                    "value_num": 36,
                    "conditions": {"voltage_v": 415},
                }
            ],
        )
        self.assertEqual(accepted["count"], 3)

    def test_document_search_and_analytics(self):
        self.assertTrue(self.catalog.search_documents("electronic trip"))
        result = self.catalog.execute_sql(
            "SELECT category, COUNT(*) AS total FROM families GROUP BY category"
        )
        self.assertEqual(len(result["rows"]), 2)
        self.assertIn("error", self.catalog.execute_sql("DELETE FROM families"))


class BoundaryTests(unittest.TestCase):
    def test_postgres_is_explicitly_pending(self):
        with self.assertRaisesRegex(NotImplementedError, "SCHEMA_PENDING"):
            PostgresBackend().list_categories()

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


if __name__ == "__main__":
    unittest.main()
