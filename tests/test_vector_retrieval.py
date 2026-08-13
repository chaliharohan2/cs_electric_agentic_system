"""Opt-in PostgreSQL/GTE integration tests.

These tests intentionally do not participate in ``make test``. Run only after
the 768-dimensional corpus embeddings have been loaded:

    CS_RUN_VECTOR_TESTS=1 python -m unittest tests.test_vector_retrieval
"""

from __future__ import annotations

import os
import unittest

from dotenv import load_dotenv

load_dotenv()

from cs_agent.backends.postgres import PostgresBackend
from cs_agent.db.refresh import inspect
from cs_agent.embeddings.factory import resolve_embedding


@unittest.skipUnless(
    os.getenv("CS_RUN_VECTOR_TESTS") == "1",
    "vector integration tests are explicitly disabled",
)
class VectorRetrievalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend = PostgresBackend()
        cls.family = os.environ["CS_VECTOR_TEST_FAMILY"]
        cls.query = os.getenv("CS_VECTOR_TEST_QUERY", "circuit breaker application")

    def test_gte_profile_and_database_are_768_dimensional(self) -> None:
        profile = resolve_embedding()
        self.assertEqual("Alibaba-NLP/gte-base-en-v1.5", profile.model)
        self.assertEqual(768, profile.dimension)
        diagnostics = inspect()
        self.assertEqual(768, diagnostics["embedding_dimension"])
        self.assertGreater(diagnostics["embeddings_loaded"], 0)

    def test_vector_result_contract_and_order(self) -> None:
        hits = self.backend.search_documents(
            query=self.query,
            family=self.family,
            chunk_types=["features", "application"],
            k=5,
        )
        self.assertTrue(hits)
        self.assertTrue(all(hit["mode"] == "vector" for hit in hits))
        self.assertTrue(
            all(
                {"chunk_type", "headings", "sku_code", "family", "brochure_md", "score"}
                <= hit.keys()
                for hit in hits
            )
        )
        scores = [hit["score"] for hit in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(
            len({hit["text"] for hit in hits}),
            len(hits),
            "md5 content deduplication must retain one row per text",
        )

    def test_filters_and_lexical_fallback_contract(self) -> None:
        no_hits = self.backend.search_documents(
            query=self.query,
            family="__definitely_not_a_real_family__",
            chunk_types=["standards"],
            k=3,
        )
        self.assertEqual([], no_hits)
        lexical = self.backend.search_documents(
            query=os.getenv("CS_VECTOR_LEXICAL_QUERY", "installation"),
            family=self.family,
            chunk_types=["installation"],
            k=3,
        )
        self.assertTrue(all(hit["mode"] in {"vector", "lexical"} for hit in lexical))
