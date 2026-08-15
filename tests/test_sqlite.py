"""SQLite catalogue unit tests (synthetic mini DB; no live Postgres required)."""

from __future__ import annotations

import json
import os
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cs_agent.backends import get_backend
from cs_agent.backends.path_levels import LEVEL_COLUMNS, NA, path_to_levels
from cs_agent.backends.sqlite import SqliteBackend


def _build_mini_catalog(path: Path) -> None:
    conn = sqlite3.connect(path)
    level_defs = ",\n".join(f"{c} TEXT NOT NULL DEFAULT '{NA}'" for c in LEVEL_COLUMNS)
    conn.executescript(
        f"""
        CREATE TABLE sku_fact (
          row_id INTEGER PRIMARY KEY,
          is_sentinel INTEGER NOT NULL,
          sku_code TEXT NOT NULL,
          canonical_code TEXT NOT NULL,
          product_id INTEGER,
          family TEXT NOT NULL,
          description TEXT,
          url TEXT,
          {level_defs},
          path_depth INTEGER NOT NULL,
          path_text TEXT NOT NULL,
          is_no_category INTEGER NOT NULL,
          price_status TEXT,
          price_quotable INTEGER,
          price_inr REAL,
          price_list TEXT,
          price_source_pdf TEXT,
          price_source_page INTEGER,
          price_effective_date TEXT,
          price_context_ok INTEGER,
          price_observations TEXT,
          peer_group TEXT,
          comparable_on TEXT,
          related_codes TEXT,
          also_published_as TEXT,
          alias_reason TEXT,
          decoded TEXT,
          attributes TEXT,
          market_segments TEXT,
          market_segments_text TEXT,
          brochure_md TEXT,
          product_page_url TEXT,
          pricelist_refs TEXT,
          sources TEXT,
          headings TEXT,
          spec_ids TEXT,
          chunk_types TEXT,
          extraction_missing TEXT,
          extraction_confidence TEXT,
          fact_count INTEGER NOT NULL,
          derived TEXT,
          fact_id TEXT,
          spec_id TEXT,
          spec_label TEXT,
          unit TEXT,
          is_canonical_spec INTEGER,
          value_num REAL,
          value_min REAL,
          value_max REAL,
          value_display TEXT,
          value_kind TEXT,
          source_of_truth TEXT,
          fact_source_pdf TEXT,
          fact_source_page INTEGER,
          fact_source_heading TEXT,
          fact_sentence TEXT
        );
        CREATE TABLE chunk (
          chunk_id INTEGER PRIMARY KEY,
          product_id INTEGER,
          sku_code TEXT NOT NULL,
          family TEXT NOT NULL,
          {level_defs},
          path_text TEXT NOT NULL,
          chunk_type TEXT NOT NULL,
          headings TEXT,
          content TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          content_len INTEGER NOT NULL,
          brochure_md TEXT,
          embedding BLOB
        );
        CREATE VIRTUAL TABLE chunk_fts USING fts5(
          content, content='chunk', content_rowid='chunk_id',
          tokenize='porter unicode61'
        );
        CREATE TABLE build_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )

    def levels(path: list[str]) -> dict[str, str]:
        return path_to_levels(path)

    path_a = ["Low Voltage", "Breakers", "MCCB"]
    la = levels(path_a)
    # CG24025W aliases to CG24025WNR
    rows = [
        # two facts for one SKU
        {
            "is_sentinel": 0,
            "sku_code": "CG24025WNR",
            "canonical_code": "CG24025WNR",
            "product_id": 1,
            "family": "MCCB",
            "description": "WiNbreak moulded case breaker 25A",
            "url": None,
            **la,
            "path_depth": 3,
            "path_text": " > ".join(path_a),
            "is_no_category": 0,
            "price_status": "listed",
            "price_quotable": 1,
            "price_inr": 1000.0,
            "price_list": "LV",
            "price_source_pdf": "p.pdf",
            "price_source_page": 1,
            "price_effective_date": "2026-01-01",
            "price_context_ok": 1,
            "price_observations": json.dumps(
                [
                    {
                        "price": 1000.0,
                        "price_list": "LV",
                        "source_pdf": "p.pdf",
                        "source_page": 1,
                        "effective_date": "2026-01-01",
                        "observation_status": "listed",
                        "context": "CG24025WNR",
                        "context_names_own_code": True,
                    }
                ]
            ),
            "peer_group": "pg1",
            "comparable_on": json.dumps(["rated_current"]),
            "related_codes": json.dumps([]),
            "also_published_as": json.dumps(["CG24025W"]),
            "alias_reason": "pricelist prints NR suffix",
            "decoded": json.dumps({}),
            "attributes": json.dumps({}),
            "market_segments": json.dumps(["Commercial"]),
            "market_segments_text": "Commercial",
            "brochure_md": "MCCB.md",
            "product_page_url": None,
            "pricelist_refs": json.dumps([]),
            "sources": json.dumps([]),
            "headings": json.dumps([]),
            "spec_ids": json.dumps(["rated_current", "breaking_capacity"]),
            "chunk_types": json.dumps(["standards", "features"]),
            "extraction_missing": json.dumps([]),
            "extraction_confidence": "high",
            "fact_count": 2,
            "derived": json.dumps({}),
            "fact_id": "rated_current",
            "spec_id": "rated_current",
            "spec_label": "Rated current",
            "unit": "A",
            "is_canonical_spec": 1,
            "value_num": 25.0,
            "value_min": None,
            "value_max": None,
            "value_display": "25 A",
            "value_kind": "scalar",
            "source_of_truth": "brochure",
            "fact_source_pdf": None,
            "fact_source_page": None,
            "fact_source_heading": None,
            "fact_sentence": "Rated current 25 A",
        },
        {
            "is_sentinel": 0,
            "sku_code": "CG24025WNR",
            "canonical_code": "CG24025WNR",
            "product_id": 1,
            "family": "MCCB",
            "description": "WiNbreak moulded case breaker 25A",
            "url": None,
            **la,
            "path_depth": 3,
            "path_text": " > ".join(path_a),
            "is_no_category": 0,
            "price_status": "listed",
            "price_quotable": 1,
            "price_inr": 1000.0,
            "price_list": "LV",
            "price_source_pdf": "p.pdf",
            "price_source_page": 1,
            "price_effective_date": "2026-01-01",
            "price_context_ok": 1,
            "price_observations": json.dumps(
                [
                    {
                        "price": 1000.0,
                        "price_list": "LV",
                        "source_pdf": "p.pdf",
                        "source_page": 1,
                        "effective_date": "2026-01-01",
                        "observation_status": "listed",
                        "context": "CG24025WNR",
                        "context_names_own_code": True,
                    }
                ]
            ),
            "peer_group": "pg1",
            "comparable_on": json.dumps(["rated_current"]),
            "related_codes": json.dumps([]),
            "also_published_as": json.dumps(["CG24025W"]),
            "alias_reason": "pricelist prints NR suffix",
            "decoded": json.dumps({}),
            "attributes": json.dumps({}),
            "market_segments": json.dumps(["Commercial"]),
            "market_segments_text": "Commercial",
            "brochure_md": "MCCB.md",
            "product_page_url": None,
            "pricelist_refs": json.dumps([]),
            "sources": json.dumps([]),
            "headings": json.dumps([]),
            "spec_ids": json.dumps(["rated_current", "breaking_capacity"]),
            "chunk_types": json.dumps(["standards", "features"]),
            "extraction_missing": json.dumps([]),
            "extraction_confidence": "high",
            "fact_count": 2,
            "derived": json.dumps({}),
            "fact_id": "breaking_capacity",
            "spec_id": "breaking_capacity",
            "spec_label": "Breaking capacity",
            "unit": "kA",
            "is_canonical_spec": 1,
            "value_num": 36.0,
            "value_min": None,
            "value_max": None,
            "value_display": "36 kA",
            "value_kind": "scalar",
            "source_of_truth": "brochure",
            "fact_source_pdf": None,
            "fact_source_page": None,
            "fact_source_heading": None,
            "fact_sentence": "Breaking capacity 36 kA",
        },
        # second SKU — multiple_variants / not quotable
        {
            "is_sentinel": 0,
            "sku_code": "WX100",
            "canonical_code": "WX100",
            "product_id": 2,
            "family": "MCCB",
            "description": "Peer breaker",
            "url": None,
            **la,
            "path_depth": 3,
            "path_text": " > ".join(path_a),
            "is_no_category": 0,
            "price_status": "multiple_variants",
            "price_quotable": 0,
            "price_inr": None,
            "price_list": None,
            "price_source_pdf": None,
            "price_source_page": None,
            "price_effective_date": None,
            "price_context_ok": 0,
            "price_observations": json.dumps(
                [
                    {
                        "price": 50.0,
                        "price_list": "LV",
                        "source_pdf": "p.pdf",
                        "source_page": 2,
                        "effective_date": None,
                        "observation_status": "multiple_variants",
                        "context": "OTHER",
                        "context_names_own_code": False,
                    }
                ]
            ),
            "peer_group": "pg1",
            "comparable_on": json.dumps(["rated_current"]),
            "related_codes": json.dumps([]),
            "also_published_as": json.dumps([]),
            "alias_reason": None,
            "decoded": json.dumps({}),
            "attributes": json.dumps({}),
            "market_segments": json.dumps([]),
            "market_segments_text": None,
            "brochure_md": "MCCB.md",
            "product_page_url": None,
            "pricelist_refs": json.dumps([]),
            "sources": json.dumps([]),
            "headings": json.dumps([]),
            "spec_ids": json.dumps(["rated_current"]),
            "chunk_types": json.dumps(["features"]),
            "extraction_missing": json.dumps([]),
            "extraction_confidence": "high",
            "fact_count": 1,
            "derived": json.dumps({}),
            "fact_id": "rated_current",
            "spec_id": "rated_current",
            "spec_label": "Rated current",
            "unit": "A",
            "is_canonical_spec": 1,
            "value_num": 100.0,
            "value_min": None,
            "value_max": None,
            "value_display": "100 A",
            "value_kind": "scalar",
            "source_of_truth": "brochure",
            "fact_source_pdf": None,
            "fact_source_page": None,
            "fact_source_heading": None,
            "fact_sentence": "Rated current 100 A",
        },
    ]
    cols = list(rows[0].keys())
    conn.executemany(
        f"INSERT INTO sku_fact ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
        [tuple(r[c] for c in cols) for r in rows],
    )
    emb = struct.pack("3f", 1.0, 0.0, 0.0)
    conn.execute(
        f"""
        INSERT INTO chunk (
          chunk_id, product_id, sku_code, family,
          {','.join(LEVEL_COLUMNS)}, path_text, chunk_type, headings,
          content, content_hash, content_len, brochure_md, embedding
        ) VALUES (1, 1, 'CG24025WNR', 'MCCB', ?, ?, ?, ?, ?, 'features', '[]',
                  'installation guidance for MCCB', 'abc', 30, 'MCCB.md', ?)
        """,
        [la[c] for c in LEVEL_COLUMNS] + [" > ".join(path_a), emb],
    )
    conn.execute("INSERT INTO chunk_fts(chunk_fts) VALUES('rebuild')")
    meta = {
        "embeddings_loaded": False,
        "embedding_dimension": 3,
        "compiled_path_depth": len(LEVEL_COLUMNS),
    }
    for key, value in meta.items():
        conn.execute(
            "INSERT INTO build_meta(key, value) VALUES (?, ?)",
            (key, json.dumps(value)),
        )
    conn.commit()
    conn.close()


class SqliteBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._tmpdir.name) / "mini.sqlite"
        _build_mini_catalog(cls.db_path)
        cls.backend = SqliteBackend(cls.db_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def test_count_products_not_fact_rows(self) -> None:
        result = self.backend.execute_sql(
            "SELECT count(DISTINCT sku_code) AS n FROM sku_fact"
        )
        self.assertEqual(2, result["rows"][0][0])
        bad = self.backend.execute_sql("SELECT count(*) AS n FROM sku_fact")
        self.assertEqual(3, bad["rows"][0][0])

    def test_resolve_alias_and_spacing(self) -> None:
        for query in ("CG24025W", "CG 24 025 W", "CG24025WNR", "cg-24025w"):
            result = self.backend.resolve_product(query=query, limit=5)
            self.assertTrue(result["hits"], msg=query)
            self.assertEqual("CG24025WNR", result["hits"][0]["sku_code"])

    def test_search_documents_requires_filter(self) -> None:
        result = self.backend.search_documents(query="installation")
        self.assertEqual("none", result[0]["mode"])
        self.assertIn("requires", result[0]["error"])

    def test_price_multiple_variants_not_quotable(self) -> None:
        detail = self.backend.get_price_detail(["WX100"])
        self.assertFalse(detail["prices"][0]["quotable"])
        self.assertEqual("multiple_variants", detail["prices"][0]["price_status"])

    def test_product_search_cheapest_listed_first(self) -> None:
        result = self.backend.product_search(family="MCCB", limit=10)
        self.assertGreaterEqual(result["total_matched"], 1)
        first = result["hits"][0]
        self.assertEqual("CG24025WNR", first["sku_code"])
        self.assertEqual(1000.0, first["price_inr"])
        self.assertTrue(first["price_quotable"])

    def test_product_search_numeric_filter(self) -> None:
        result = self.backend.product_search(
            family="MCCB",
            filters=[{"spec_id": "rated_current", "op": "eq", "value": 25}],
        )
        self.assertEqual(1, result["total_matched"])
        self.assertEqual("CG24025WNR", result["hits"][0]["sku_code"])

    def test_compare_peer_group(self) -> None:
        result = self.backend.compare_skus(["CG24025WNR", "WX100"], None)
        self.assertTrue(result["peer_group_match"])
        self.assertIn("rated_current", result["axes"])


class BackendSelectorTests(unittest.TestCase):
    def test_postgres_is_not_a_runtime_backend(self) -> None:
        with patch.dict(os.environ, {"CS_BACKEND": "postgres"}):
            with self.assertRaisesRegex(ValueError, "sqlite"):
                get_backend()


if __name__ == "__main__":
    unittest.main()
