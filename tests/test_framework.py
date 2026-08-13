import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from cs_agent.backends import FixturesBackend, PostgresBackend
from cs_agent.embeddings.factory import embed
from cs_agent.graph import build_graph
from cs_agent.graph.nodes.composer import composer
from cs_agent.graph.nodes.record_evidence import _extract, record_evidence
from cs_agent.graph.state import Evidence
from cs_agent.observability import AgentCallbackHandler, TraceLogger
from cs_agent.subgraphs.analytics.build import (
    _after_analyst,
    _after_record,
    build_analytics_graph,
)
from cs_agent.subgraphs.analytics.nodes import (
    AnalyticsReport,
    execute_analytics_sql,
    record_queries,
)
from cs_agent.subgraphs.analytics.tool import _max_queries
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

    def test_text_fields_match_partially_and_case_insensitively(self):
        self.assertTrue(self.catalog.list_canonical_specs("MCCB"))
        families = self.catalog.taxonomy_browse("mccb")["families"]
        self.assertTrue(families)
        self.assertTrue(self.catalog.product_search(category="MCCB"))
        self.assertTrue(self.catalog.product_search(text="win2-125"))
        partial = self.catalog.get_sku("win2-125-3p", ["facts"])
        self.assertEqual(partial["sku_code"], "WIN2-125-3P-63")
        comparison = self.catalog.compare_skus(
            ["win2-125-3p-63", "does-not-exist"], ["rated_current"]
        )
        self.assertEqual(comparison["sku_codes"], ["WIN2-125-3P-63"])
        self.assertEqual(comparison["unresolved_sku_codes"], ["does-not-exist"])
        self.assertEqual(comparison["rows"][0]["spec_id"], "rated_current_a")

    def test_punctuation_and_word_order_variants_still_match(self):
        for spelling in ("WIN2-125", "win2 125", "125 win2", "WIN2125", "win2\u2013125"):
            self.assertTrue(
                self.catalog.product_search(text=spelling),
                f"{spelling!r} returned no hits",
            )

    def test_taxonomy_browse_honours_family_without_category(self):
        result = self.catalog.taxonomy_browse(family="WIN2-125")
        self.assertEqual(result["level"], "facets")
        self.assertEqual(result["matched_families"], ["WIN2-125"])
        self.assertEqual(result["sku_count"], 2)

    def test_unmatched_name_suggests_real_catalogue_names(self):
        missing = self.catalog.product_search(text="WIN2-999")
        self.assertEqual(missing["hits"], [])
        self.assertIn("WIN2-125", missing["suggestions"]["families"])

    def test_out_of_range_filter_blames_the_filter_not_the_name(self):
        excluded = self.catalog.product_search(
            category="protection/mccb",
            filters=[{"spec_id": "icu_ka", "op": "gte", "value": 9000}],
        )
        self.assertEqual(excluded["hits"], [])
        self.assertIn("none satisfy the filters", excluded["no_matches"])
        self.assertNotIn("suggestions", excluded)

    def test_compare_skus_redirects_product_line_names_to_product_search(self):
        comparison = self.catalog.compare_skus(["contactor 09", "contactor 18"])
        self.assertIn("ordering codes", comparison["error"])
        self.assertIn(
            "switching/contactor",
            comparison["suggestions"]["contactor 09"]["categories"],
        )

    def test_spec_ids_match_their_labels(self):
        hits = self.catalog.product_search(
            category="protection/mccb", return_specs=["rated current"]
        )
        self.assertEqual(
            {fact["spec_id"] for hit in hits for fact in hit["specs"]},
            {"rated_current_a"},
        )

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

    def test_analytics_query_cap_defaults_and_validates_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_max_queries(), 4)
        for invalid in ("not-a-number", "0", "-2"):
            with patch.dict(
                os.environ, {"CS_ANALYTICS_MAX_QUERIES": invalid}, clear=True
            ):
                self.assertEqual(_max_queries(), 4)
        with patch.dict(
            os.environ, {"CS_ANALYTICS_MAX_QUERIES": "6"}, clear=True
        ):
            self.assertEqual(_max_queries(), 6)

    def test_analytics_routes_one_query_when_budget_remains(self):
        call = {
            "name": "execute_analytics_sql",
            "args": {"sql": "SELECT 1"},
            "id": "query-1",
            "type": "tool_call",
        }
        self.assertEqual(
            _after_analyst(
                {
                    "messages": [AIMessage(content="", tool_calls=[call])],
                    "query_count": 2,
                    "max_queries": 4,
                }
            ),
            "query",
        )
        self.assertEqual(
            _after_analyst(
                {
                    "messages": [AIMessage(content="", tool_calls=[call])],
                    "query_count": 4,
                    "max_queries": 4,
                }
            ),
            "summarize",
        )

    def test_analytics_can_finish_early_and_hard_stops_at_cap(self):
        self.assertEqual(
            _after_analyst(
                {
                    "messages": [AIMessage(content="Analysis complete.")],
                    "query_count": 1,
                    "max_queries": 4,
                }
            ),
            "summarize",
        )
        self.assertEqual(
            _after_record({"query_count": 4, "max_queries": 4}), "summarize"
        )
        self.assertEqual(
            _after_record({"query_count": 3, "max_queries": 4}), "analyst"
        )

    def test_failed_analytics_query_consumes_budget(self):
        update = record_queries(
            {
                "messages": [
                    ToolMessage(
                        content=json.dumps({"error": "bad SQL"}),
                        name="execute_analytics_sql",
                        tool_call_id="query-1",
                    )
                ],
                "query_count": 2,
            }
        )
        self.assertEqual(update["query_count"], 3)

    def test_private_analytics_tool_rejects_non_select_sql(self):
        result = execute_analytics_sql("DELETE FROM in_use.mv_fact")
        self.assertIn("read-only SELECT", result["error"])

    def test_analytics_graph_and_structured_report_contract(self):
        graph = build_analytics_graph().get_graph()
        self.assertEqual(
            {"prepare", "analyst", "query", "record_queries", "summarize"},
            set(graph.nodes) - {"__start__", "__end__"},
        )
        report = AnalyticsReport.model_validate(
            {
                "summary": "There are 12 matching SKUs.",
                "evidence": [
                    {
                        "statement": "There are 12 matching SKUs.",
                        "value_num": 12,
                        "value_display": "12",
                    }
                ],
                "queries_run": 2,
                "limitations": ["Three SKUs had no published price."],
            }
        )
        self.assertEqual(report.evidence[0].value_num, 12)

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

    def test_empty_recomposition_keeps_the_previous_draft(self):
        class Empty:
            content = "   "

        with patch("cs_agent.graph.nodes.composer.get_model") as get_model:
            get_model.return_value.invoke.return_value = Empty()
            update = composer(
                {
                    "messages": [],
                    "evidence": [],
                    "draft": "The earlier answer.",
                    "validation": {"errors": ["Unsupported numeric claim(s) ['9']"]},
                }
            )
        self.assertEqual(update["draft"], "The earlier answer.")

    def test_catalogue_counts_and_bounds_are_citable(self):
        evidence = _extract(
            [
                {
                    "category": "ACB – WiNmaster 3",
                    "spec_id": "breaking_capacity_ka",
                    "unit": "kA",
                    "sku_count": 140,
                    "observed_min": 42,
                    "observed_max": 100,
                }
            ],
            "list_canonical_specs",
        )
        for claim in (
            "The category carries 140 SKUs.",
            "Breaking capacity runs from 42 kA to 100 kA.",
            "The observed maximum is 100.",
        ):
            self.assertTrue(
                validate_numeric_fidelity(claim, evidence).passed, claim
            )
        self.assertFalse(
            validate_numeric_fidelity("Breaking capacity reaches 250 kA.", evidence).passed
        )

    def test_grouped_prices_are_read_as_one_number(self):
        evidence = _extract(
            [
                {
                    "category": "ACB – WiNmaster 2",
                    "spec_id": "price_inr",
                    "unit": "INR",
                    "sku_count": 101,
                    "observed_min": 1600,
                    "observed_max": 875990,
                }
            ],
            "list_canonical_specs",
        )
        for claim in (
            "MRP runs from 1,600 to 8,75,990.",
            "MRP runs from 1,600 to 875,990.",
            "The dearest SKU is 875990.",
        ):
            self.assertTrue(validate_numeric_fidelity(claim, evidence).passed, claim)
        # Grouping must not swallow a comma-separated list into one figure.
        self.assertEqual(
            validate_numeric_fidelity("Poles are 3, 4 and 5.", evidence).numbers_total,
            3,
        )

    def test_the_word_is_before_a_figure_is_not_a_standard_reference(self):
        evidence = _extract(
            {
                "level": "facets",
                "family": "ACB – WiNmaster 3",
                "axes": {"rating_idx": [{"code": "08", "meaning": "800", "sku_count": 22}]},
            },
            "taxonomy_browse",
        )
        supported = validate_numeric_fidelity("The rated current is 800 A.", evidence)
        self.assertEqual(supported.numbers_total, 1)
        self.assertTrue(supported.passed)
        invented = validate_numeric_fidelity("The rated current is 900 A.", evidence)
        self.assertEqual(invented.numbers_total, 1)
        self.assertFalse(invented.passed)
        # A genuine standard reference is still not a measurement.
        self.assertEqual(
            validate_numeric_fidelity("Tested to IS 13947-2.", evidence).numbers_total,
            0,
        )

    def test_section_numbers_are_not_measurements(self):
        for heading in ("### 5. ACB Type (mechanism)", "7) Accessories", "2. Poles"):
            result = validate_numeric_fidelity(heading, [])
            self.assertEqual(result.numbers_total, 0, heading)
            self.assertTrue(result.passed, heading)
        # A real reading on its own still has to be backed by evidence.
        self.assertFalse(validate_numeric_fidelity("Rated at 630 A", []).passed)

    def test_price_carries_its_currency_from_the_leading_symbol(self):
        evidence = _extract(
            {
                "sku_code": "WX12N4PEDOA(S)",
                "facts": [
                    {
                        "spec_id": "price_inr",
                        "spec_label": "MRP",
                        "unit": "INR",
                        "value_num": 579370.0,
                        "value_kind": "scalar",
                    }
                ],
            },
            "get_sku",
        )
        for claim in ("It lists at ₹5,79,370.", "It lists at Rs 5,79,370."):
            self.assertTrue(validate_numeric_fidelity(claim, evidence).passed, claim)
        self.assertFalse(
            validate_numeric_fidelity("It lists at ₹5,79,999.", evidence).passed
        )

    def test_digits_in_a_product_name_are_not_numeric_claims(self):
        evidence = _extract(
            {
                "level": "families",
                "families": [{"category": "ACB – WiNmaster 2", "sku_count": 101}],
            },
            "taxonomy_browse",
        )
        # The name is retrieved with an en dash; the answer may retype it as ASCII.
        self.assertTrue(
            validate_numeric_fidelity(
                "ACB - WiNmaster 2 lists 101 SKUs.", evidence
            ).passed
        )
        self.assertFalse(
            validate_numeric_fidelity(
                "ACB – WiNmaster 2 lists 999 SKUs.", evidence
            ).passed
        )

    def test_evidence_parser_reads_compare_facts(self):
        payload = FixturesBackend().compare_skus(
            ["WIN2-125-3P-63", "WIN2-250-4P-250"], ["rated_current_a"]
        )
        records = _extract(payload, "compare_skus")
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record["spec_id"] == "rated_current_a" for record in records))

    def test_evidence_parser_reads_structured_analytics_report(self):
        records = _extract(
            {
                "summary": "The median price is ₹12,500.",
                "evidence": [
                    {
                        "statement": "The median price is ₹12,500.",
                        "value_num": 12500,
                        "value_display": "₹12,500",
                        "unit": "INR",
                        "spec_id": "price_inr",
                    }
                ],
                "queries_run": 3,
                "limitations": ["POR prices were excluded."],
                "error": None,
            },
            "analytics_query",
        )
        numeric = next(record for record in records if record["value_num"] is not None)
        self.assertEqual(numeric["value_num"], 12500)
        self.assertEqual(numeric["unit"], "INR")
        self.assertEqual(numeric["source_of_truth"], "analytics_query")
        self.assertTrue(
            validate_numeric_fidelity("The median price is ₹12,500.", records).passed
        )
        self.assertTrue(any(record["text"] == "POR prices were excluded." for record in records))

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
    def test_terminal_trace_is_concise_but_jsonl_stays_detailed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            screen = io.StringIO()
            with redirect_stdout(screen):
                trace = TraceLogger(file_path=path, print_to_screen=True)
                callback = AgentCallbackHandler(trace)
                TOOLS_BY_NAME["taxonomy_browse"].invoke(
                    {"category": None, "family": None},
                    config={"callbacks": [callback]},
                )
                trace.event(
                    "state.update",
                    node="validator",
                    update={
                        "validation": {
                            "passed": True,
                            "numbers_total": 2,
                            "matched": 2,
                            "action": "accepted",
                        }
                    },
                )
                trace.close()

            terminal = screen.getvalue()
            self.assertIn("🔧 taxonomy_browse", terminal)
            self.assertIn("✓ taxonomy_browse:", terminal)
            self.assertIn("[validator] validation: passed", terminal)
            self.assertNotIn("[TRACE]", terminal)
            self.assertNotIn("callback_run_id", terminal)

            records = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            tool_end = next(record for record in records if record["event"] == "tool.end")
            self.assertIn("output", tool_end)
            self.assertIn("callback_run_id", tool_end)

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
