"""SQLite/GTE integration tests against the built catalogue artifact.

These run as part of ``make test``. They need the catalogue built with
768-dimensional embeddings loaded, which is the normal state of the artifact.
Set ``CS_SKIP_VECTOR_TESTS=1`` to opt out when working without one.

The test family defaults to a range with plenty of embedded ``features`` and
``application`` chunks and a populated ``installation`` set, so the vector and
lexical paths both have something to retrieve. Override with
``CS_VECTOR_TEST_FAMILY`` after a rebuild changes the catalogue's shape.
"""

from __future__ import annotations

import os
import unittest

from dotenv import load_dotenv

load_dotenv()

from cs_agent.backends.sqlite import SqliteBackend
from cs_agent.embeddings.factory import resolve_embedding

DEFAULT_TEST_FAMILY = "MCCB – Winbreak1"


@unittest.skipIf(
    os.getenv("CS_SKIP_VECTOR_TESTS") == "1",
    "vector integration tests explicitly skipped via CS_SKIP_VECTOR_TESTS",
)
class VectorRetrievalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend = SqliteBackend()
        cls.family = os.getenv("CS_VECTOR_TEST_FAMILY") or DEFAULT_TEST_FAMILY
        cls.query = os.getenv("CS_VECTOR_TEST_QUERY", "circuit breaker application")

    def test_gte_profile_and_catalogue_are_768_dimensional(self) -> None:
        profile = resolve_embedding()
        self.assertEqual("Alibaba-NLP/gte-base-en-v1.5", profile.model)
        self.assertEqual(768, profile.dimension)
        self.assertTrue(self.backend._meta("embeddings_loaded"))
        self.assertEqual(768, int(self.backend._meta("embedding_dimension")))
        self.assertTrue(self.backend.vec_available)

    def test_vector_result_contract_and_order(self) -> None:
        hits = self.backend.search_documents(
            query=self.query,
            family=self.family,
            chunk_types=["features", "application"],
            k=5,
        )
        self.assertTrue(hits)
        # `mode` is gone; a `distance` is what the semantic index leaves behind,
        # and it is what tells the reader which scale `score` is on.
        self.assertTrue(all("distance" in hit for hit in hits))
        self.assertTrue(all("mode" not in hit for hit in hits))
        self.assertTrue(all("chunk_id" not in hit for hit in hits))
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
        self.assertTrue(all("mode" not in hit for hit in lexical))
        self.assertTrue(all("score" in hit for hit in lexical))
