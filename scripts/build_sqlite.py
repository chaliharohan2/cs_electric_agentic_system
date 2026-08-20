#!/usr/bin/env python3
"""Build the read-only SQLite catalogue artifact from Postgres mv_* views.

Usage:
  source ../venv/bin/activate
  python scripts/build_sqlite.py
  python scripts/build_sqlite.py --output artifacts/catalog-2026-08-14.sqlite
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import struct
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cs_agent.backends.path_levels import (  # noqa: E402
    COMPILED_PATH_DEPTH,
    LEVEL_COLUMNS,
    NA,
    path_to_levels,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_sqlite")

REQUIRED_VIEWS = (
    "mv_sku",
    "mv_fact",
    "mv_price",
    "mv_source",
    "mv_code_alias",
    "mv_chunk_index",
)


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return list(value)


def _as_path(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(part) for part in value if part is not None]
    return []


def _connect_pg(database_url: str):
    connection = psycopg.connect(database_url, row_factory=dict_row)
    register_vector(connection)
    return connection


def _preflight(pg) -> dict[str, Any]:
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT matviewname FROM pg_matviews
            WHERE schemaname = 'in_use' ORDER BY 1
            """
        )
        present = {row["matviewname"] for row in cur.fetchall()}
        missing = [name for name in REQUIRED_VIEWS if name not in present]
        if missing:
            raise RuntimeError(f"Missing materialized views: {missing}")

        cur.execute(
            """
            SELECT max(jsonb_array_length(
                     CASE WHEN jsonb_typeof(taxonomy->'path') = 'array'
                          THEN taxonomy->'path' ELSE '[]'::jsonb END
                   )) AS max_depth
            FROM in_use.product_chunks WHERE is_active
            """
        )
        max_depth = int(cur.fetchone()["max_depth"] or 0)
        if max_depth > COMPILED_PATH_DEPTH:
            raise RuntimeError(
                f"Path depth {max_depth} exceeds compiled column count "
                f"{COMPILED_PATH_DEPTH}; widen LEVEL_COLUMNS and rebuild."
            )
        if max_depth < COMPILED_PATH_DEPTH:
            logger.warning(
                "Observed max path depth %s < compiled %s; unused levels stay %r",
                max_depth,
                COMPILED_PATH_DEPTH,
                NA,
            )

        cur.execute("SELECT count(*) AS n FROM in_use.mv_sku")
        sku_count = int(cur.fetchone()["n"])
        cur.execute("SELECT count(*) AS n FROM in_use.mv_fact")
        fact_count = int(cur.fetchone()["n"])
        cur.execute("SELECT count(*) AS n FROM in_use.product_chunks WHERE is_active")
        chunk_count = int(cur.fetchone()["n"])
        cur.execute(
            """
            SELECT count(*) AS n FROM in_use.product_chunks
            WHERE is_active AND product_id IS NOT NULL
            """
        )
        chunk_with_product = int(cur.fetchone()["n"])
        cur.execute(
            """
            SELECT count(DISTINCT product->>'sku_code') AS n
            FROM in_use.product_chunks
            WHERE is_active AND product_id IS NOT NULL
              AND product->>'sku_code' IS NOT NULL
            """
        )
        distinct_products = int(cur.fetchone()["n"])
        # mv_sku is one row per ordering code. Comparing against distinct
        # product_id instead hid 544 codes that share one: the counts differed
        # and the warning read as a rounding quirk rather than dropped products.
        if sku_count != distinct_products:
            logger.warning(
                "mv_sku count %s != distinct active sku_code %s",
                sku_count,
                distinct_products,
            )

    return {
        "max_depth": max_depth,
        "sku_count": sku_count,
        "fact_count": fact_count,
        "chunk_count": chunk_count,
        "chunk_with_product": chunk_with_product,
    }


def _create_schema(conn: sqlite3.Connection) -> None:
    level_defs = ",\n  ".join(
        f"{col} TEXT NOT NULL DEFAULT '{NA}'" for col in LEVEL_COLUMNS
    )
    conn.executescript(
        f"""
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;
        PRAGMA temp_store = MEMORY;

        DROP TABLE IF EXISTS build_meta;
        DROP TABLE IF EXISTS chunk_fts;
        DROP TABLE IF EXISTS chunk;
        DROP TABLE IF EXISTS taxonomy_level;
        DROP TABLE IF EXISTS sku_fact;

        CREATE TABLE sku_fact (
          row_id                INTEGER PRIMARY KEY,
          is_sentinel           INTEGER NOT NULL,
          sku_code              TEXT NOT NULL,
          canonical_code        TEXT NOT NULL,
          product_id            INTEGER,
          family                TEXT NOT NULL,
          description           TEXT,
          url                   TEXT,
          {level_defs},
          path_depth            INTEGER NOT NULL,
          path_text             TEXT NOT NULL,
          is_no_category        INTEGER NOT NULL,
          price_status          TEXT,
          price_quotable        INTEGER,
          price_inr             REAL,
          price_list            TEXT,
          price_source_pdf      TEXT,
          price_source_page     INTEGER,
          price_effective_date  TEXT,
          price_context_ok      INTEGER,
          price_sibling_code    TEXT,
          price_observations    TEXT,
          peer_group            TEXT,
          comparable_on         TEXT,
          related_codes         TEXT,
          also_published_as     TEXT,
          alias_reason          TEXT,
          decoded               TEXT,
          attributes            TEXT,
          market_segments       TEXT,
          market_segments_text  TEXT,
          brochure_md           TEXT,
          product_page_url      TEXT,
          pricelist_refs        TEXT,
          sources               TEXT,
          headings              TEXT,
          spec_ids              TEXT,
          chunk_types           TEXT,
          extraction_missing    TEXT,
          extraction_confidence TEXT,
          fact_count            INTEGER NOT NULL,
          derived               TEXT,
          fact_id               TEXT,
          spec_id               TEXT,
          spec_label            TEXT,
          unit                  TEXT,
          is_canonical_spec     INTEGER,
          value_num             REAL,
          value_min             REAL,
          value_max             REAL,
          value_display         TEXT,
          value_kind            TEXT,
          source_of_truth       TEXT,
          fact_source_pdf       TEXT,
          fact_source_page      INTEGER,
          fact_source_heading   TEXT,
          fact_sentence         TEXT
        );

        CREATE TABLE taxonomy_level (
          path_text        TEXT PRIMARY KEY,
          name             TEXT NOT NULL,
          level            INTEGER NOT NULL,
          url              TEXT,
          description      TEXT,
          is_leaf          INTEGER,
          page_type        TEXT
        );

        CREATE TABLE chunk (
          chunk_id         INTEGER PRIMARY KEY,
          product_id       INTEGER,
          sku_code         TEXT NOT NULL,
          family           TEXT NOT NULL,
          {level_defs},
          path_text        TEXT NOT NULL,
          chunk_type       TEXT NOT NULL,
          headings         TEXT,
          content          TEXT NOT NULL,
          content_hash     TEXT NOT NULL,
          content_len      INTEGER NOT NULL,
          brochure_md      TEXT,
          embedding        BLOB
        );
        """
    )


def _summarize_price(
    price_status: str | None, observations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Collapse a SKU's price observations into the quotability summary.

    Quotability turns on the published status and the presence of a figure.
    It deliberately does NOT turn on the pricelist header text: that header
    names the table, not the row, so testing it suppressed all but one price
    in the catalogue (see the comment on mv_price in cs_agent/db/views.sql).

    A header naming a *different* ordering code is still recorded, on the SKU
    as price_sibling_code and on each observation, because it marks the
    multi-column binding defect where a code can inherit a sibling's price.
    """
    priced = [o for o in observations if o.get("price") is not None]
    quotable = price_status != "multiple_variants" and bool(priced)
    context_ok_any = any(bool(o.get("context_names_own_code")) for o in observations)
    sibling_codes = [
        str(o["context_sibling_code"])
        for o in observations
        if o.get("context_sibling_code")
    ]

    # Prefer an observation whose own header names this SKU; those are rare, so
    # fall back to the first figure rather than reporting no price at all.
    best = next(
        (o for o in priced if o.get("context_names_own_code")),
        priced[0] if priced else None,
    )
    return {
        "price_quotable": int(bool(quotable)),
        "price_inr": float(best["price"]) if best else None,
        "price_list": best.get("price_list") if best else None,
        "price_source_pdf": best.get("source_pdf") if best else None,
        "price_source_page": best.get("source_page") if best else None,
        "price_effective_date": best.get("effective_date") if best else None,
        "price_context_ok": int(bool(context_ok_any)) if observations else None,
        "price_sibling_code": sibling_codes[0] if sibling_codes else None,
        "price_observations": _json_dump(
            [
                {
                    "price": float(o["price"]) if o.get("price") is not None else None,
                    "price_list": o.get("price_list"),
                    "source_pdf": o.get("source_pdf"),
                    "source_page": o.get("source_page"),
                    "effective_date": o.get("effective_date"),
                    "observation_status": o.get("observation_status"),
                    "context": o.get("context"),
                    "price_column": o.get("price_column"),
                    "context_names_own_code": bool(o.get("context_names_own_code")),
                    "context_sibling_code": o.get("context_sibling_code"),
                }
                for o in observations
            ]
        ),
    }


def _load_side_tables(pg) -> tuple[
    dict[int, list[dict[str, Any]]],
    dict[int, list[dict[str, Any]]],
    dict[int, list[str]],
]:
    # Keyed on sku_code, not product_id: sibling ordering codes share a
    # product_id but are separate products with their own prices and chunks.
    prices: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    chunk_types: dict[str, list[str]] = defaultdict(list)
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT sku_code, price, price_list, source_pdf, source_page,
                   effective_date, observation_status, context, price_column,
                   context_names_own_code, context_sibling_code
            FROM in_use.mv_price
            ORDER BY sku_code, source_pdf, source_page
            """
        )
        for row in cur:
            prices[str(row["sku_code"])].append(dict(row))
        cur.execute(
            """
            SELECT sku_code, ref_type, ref_name, page
            FROM in_use.mv_source
            ORDER BY sku_code, ref_type, ref_name
            """
        )
        for row in cur:
            sources[str(row["sku_code"])].append(dict(row))
        cur.execute(
            """
            SELECT sku_code, chunk_type
            FROM in_use.mv_chunk_index
            WHERE sku_code IS NOT NULL
            ORDER BY sku_code, chunk_type
            """
        )
        for row in cur:
            code = str(row["sku_code"])
            ctype = row["chunk_type"]
            if ctype not in chunk_types[code]:
                chunk_types[code].append(ctype)
    return prices, sources, chunk_types


def _sku_base_row(
    sku: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
    sources: dict[str, list[dict[str, Any]]],
    chunk_types: dict[str, list[str]],
) -> dict[str, Any]:
    product_id = int(sku["product_id"])
    code = str(sku["sku_code"])
    path = _as_path(sku.get("path"))
    levels = path_to_levels(path)
    depth = int(sku.get("depth") or len(path))
    observations = prices.get(code, [])
    price_summary = _summarize_price(sku.get("price_status"), observations)
    src_rows = sources.get(code, [])
    brochure_md = next(
        (s["ref_name"] for s in src_rows if s["ref_type"] == "brochure_md"), None
    )
    product_page_url = next(
        (s["ref_name"] for s in src_rows if s["ref_type"] == "product_page"), None
    )
    pricelist_refs = [
        {"pdf": s["ref_name"], "page": s["page"]}
        for s in src_rows
        if s["ref_type"] == "pricelist_pdf"
    ]
    segments = _as_list(sku.get("market_segments"))
    return {
        "is_sentinel": 0,
        "sku_code": sku["sku_code"],
        "canonical_code": sku["canonical_code"] or sku["sku_code"],
        "product_id": product_id,
        "family": sku.get("family") or NA,
        "description": sku.get("description"),
        "url": sku.get("url"),
        **levels,
        "path_depth": depth,
        "path_text": sku.get("path_text") or " > ".join(path),
        "is_no_category": int(bool(sku.get("is_no_category"))),
        **price_summary,
        "peer_group": sku.get("peer_group"),
        "comparable_on": _json_dump(sku.get("comparable_on")),
        "related_codes": _json_dump(sku.get("related_codes")),
        "also_published_as": _json_dump(sku.get("also_published_as")),
        "alias_reason": sku.get("alias_reason"),
        "decoded": _json_dump(sku.get("decoded")),
        "attributes": _json_dump(sku.get("attributes")),
        "market_segments": _json_dump(segments),
        "market_segments_text": "|".join(str(s) for s in segments) if segments else None,
        "brochure_md": brochure_md,
        "product_page_url": product_page_url,
        "pricelist_refs": _json_dump(pricelist_refs),
        "sources": _json_dump(sku.get("sources")),
        "headings": _json_dump(sku.get("headings")),
        "spec_ids": _json_dump(sku.get("spec_ids")),
        "chunk_types": _json_dump(chunk_types.get(code, [])),
        "extraction_missing": _json_dump(sku.get("extraction_missing")),
        "extraction_confidence": sku.get("extraction_confidence"),
        "fact_count": int(sku.get("fact_count") or 0),
        "derived": _json_dump(sku.get("derived")),
    }


SKU_FACT_COLUMNS = [
    "is_sentinel",
    "sku_code",
    "canonical_code",
    "product_id",
    "family",
    "description",
    "url",
    *LEVEL_COLUMNS,
    "path_depth",
    "path_text",
    "is_no_category",
    "price_status",
    "price_quotable",
    "price_inr",
    "price_list",
    "price_source_pdf",
    "price_source_page",
    "price_effective_date",
    "price_context_ok",
    "price_sibling_code",
    "price_observations",
    "peer_group",
    "comparable_on",
    "related_codes",
    "also_published_as",
    "alias_reason",
    "decoded",
    "attributes",
    "market_segments",
    "market_segments_text",
    "brochure_md",
    "product_page_url",
    "pricelist_refs",
    "sources",
    "headings",
    "spec_ids",
    "chunk_types",
    "extraction_missing",
    "extraction_confidence",
    "fact_count",
    "derived",
    "fact_id",
    "spec_id",
    "spec_label",
    "unit",
    "is_canonical_spec",
    "value_num",
    "value_min",
    "value_max",
    "value_display",
    "value_kind",
    "source_of_truth",
    "fact_source_pdf",
    "fact_source_page",
    "fact_source_heading",
    "fact_sentence",
]


def _insert_sku_facts(conn: sqlite3.Connection, pg, side) -> dict[str, Any]:
    prices, sources, chunk_types = side
    placeholders = ",".join("?" for _ in SKU_FACT_COLUMNS)
    col_sql = ",".join(SKU_FACT_COLUMNS)
    insert_sql = f"INSERT INTO sku_fact ({col_sql}) VALUES ({placeholders})"

    with pg.cursor() as cur:
        cur.execute("SELECT * FROM in_use.mv_sku ORDER BY sku_code")
        skus = [dict(row) for row in cur.fetchall()]

    # Keyed on the ordering code. Sibling codes such as `CE20113` and
    # `CE20113NR` share a product_id while carrying different content, so
    # keying on product_id silently kept one and dropped the other.
    sku_by_code = {str(s["sku_code"]): s for s in skus}
    if len(sku_by_code) != len(skus):
        seen: dict[str, int] = defaultdict(int)
        for sku in skus:
            seen[str(sku["sku_code"])] += 1
        raise RuntimeError(
            "mv_sku returned the same sku_code twice: "
            + ", ".join(c for c, n in seen.items() if n > 1)
        )

    alias_to_products: dict[str, set[str]] = defaultdict(set)
    for sku in skus:
        for code in {
            sku["sku_code"],
            sku["canonical_code"],
            *(_as_list(sku.get("also_published_as"))),
        }:
            if code:
                alias_to_products[str(code)].add(sku["sku_code"])
    alias_collisions = {
        code: sorted(skus_)
        for code, skus_ in alias_to_products.items()
        if len(skus_) > 1
    }

    bases = {
        code: _sku_base_row(sku, prices, sources, chunk_types)
        for code, sku in sku_by_code.items()
    }
    # fix price_status onto base (from sku)
    for code, sku in sku_by_code.items():
        bases[code]["price_status"] = sku.get("price_status")

    facts_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with pg.cursor(name="mv_fact_stream") as cur:
        cur.itersize = 5000
        cur.execute(
            """
            SELECT sku_code, spec_id, spec_label, unit, is_canonical_spec,
                   value_num, value_min, value_max, value_display, value_kind,
                   source_of_truth, source_pdf, source_page, source_heading,
                   fact_sentence
            FROM in_use.mv_fact
            ORDER BY sku_code, spec_id
            """
        )
        for row in cur:
            facts_by_code[str(row["sku_code"])].append(dict(row))

    factless: list[dict[str, str]] = []
    composite_by_family: dict[str, int] = defaultdict(int)
    sibling_price_skus: list[dict[str, str]] = []
    quotable_count = 0
    no_category_count = 0
    batch: list[tuple[Any, ...]] = []
    row_count = 0

    def flush() -> None:
        nonlocal batch
        if batch:
            conn.executemany(insert_sql, batch)
            batch = []

    for code, base in bases.items():
        if base["is_no_category"]:
            no_category_count += 1
        if base.get("price_quotable"):
            quotable_count += 1
        if base.get("price_sibling_code"):
            sibling_price_skus.append(
                {
                    "sku_code": base["sku_code"],
                    "sibling_code": base["price_sibling_code"],
                    "price_status": base.get("price_status") or "",
                }
            )
        facts = facts_by_code.get(code, [])
        if not facts:
            factless.append(
                {
                    "sku_code": base["sku_code"],
                    "family": base["family"],
                    "path_text": base["path_text"],
                }
            )
            sentinel = {
                **base,
                "is_sentinel": 1,
                "fact_id": None,
                "spec_id": None,
                "spec_label": None,
                "unit": None,
                "is_canonical_spec": None,
                "value_num": None,
                "value_min": None,
                "value_max": None,
                "value_display": None,
                "value_kind": None,
                "source_of_truth": None,
                "fact_source_pdf": None,
                "fact_source_page": None,
                "fact_source_heading": None,
                "fact_sentence": None,
            }
            batch.append(tuple(sentinel[c] for c in SKU_FACT_COLUMNS))
            row_count += 1
            if len(batch) >= 2000:
                flush()
            continue
        for fact in facts:
            if fact.get("value_kind") == "composite":
                composite_by_family[base["family"]] += 1
            row = {
                **base,
                "is_sentinel": 0,
                "fact_id": fact.get("spec_id"),
                "spec_id": fact.get("spec_id"),
                "spec_label": fact.get("spec_label"),
                "unit": fact.get("unit"),
                "is_canonical_spec": int(bool(fact.get("is_canonical_spec"))),
                "value_num": fact.get("value_num"),
                "value_min": fact.get("value_min"),
                "value_max": fact.get("value_max"),
                "value_display": fact.get("value_display"),
                "value_kind": fact.get("value_kind"),
                "source_of_truth": fact.get("source_of_truth"),
                "fact_source_pdf": fact.get("source_pdf"),
                "fact_source_page": fact.get("source_page"),
                "fact_source_heading": fact.get("source_heading"),
                "fact_sentence": fact.get("fact_sentence"),
            }
            batch.append(tuple(row[c] for c in SKU_FACT_COLUMNS))
            row_count += 1
            if len(batch) >= 2000:
                flush()
    flush()
    conn.commit()
    return {
        "sku_fact_rows": row_count,
        "distinct_skus": len(bases),
        "factless_skus": factless,
        "alias_collisions": alias_collisions,
        "composite_by_family": dict(composite_by_family),
        "sibling_price_skus": sorted(sibling_price_skus, key=lambda r: r["sku_code"]),
        "quotable_skus": quotable_count,
        "no_category_count": no_category_count,
    }


def _insert_taxonomy_levels(conn: sqlite3.Connection, pg) -> dict[str, Any]:
    """Publish the catalogue's own description and URL for each taxonomy node.

    `taxonomy.levels[]` runs parallel to `taxonomy.path`, one entry per level,
    carrying the published page URL, description, leaf flag, and a `contents[]`
    list of children with a one-line note each. A node's own `description` is
    usually null while its parent's note about it is not, so the two are merged.

    Keyed on the full path prefix rather than the name: names are not
    guaranteed unique across branches, and the browse tool looks nodes up by
    the path it is standing on.
    """
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT
              array_to_string(ARRAY(
                SELECT part FROM jsonb_array_elements_text(taxonomy->'path')
                     WITH ORDINALITY AS t(part, ord)
                WHERE ord <= (l->>'level')::int
              ), ' > ')                       AS path_text,
              l->>'name'                      AS name,
              (l->>'level')::int              AS level,
              l->>'url'                       AS url,
              NULLIF(l->>'description', '')   AS description,
              (l->>'is_leaf')::boolean        AS is_leaf,
              l->>'page_type'                 AS page_type
            FROM in_use.product_chunks
            CROSS JOIN LATERAL jsonb_array_elements(
              CASE WHEN jsonb_typeof(taxonomy->'levels') = 'array'
                   THEN taxonomy->'levels' ELSE '[]'::jsonb END
            ) AS l
            WHERE is_active
              AND jsonb_typeof(taxonomy->'path') = 'array'
              AND l->>'name' IS NOT NULL
              AND (l->>'level') ~ '^[0-9]+$'
            """
        )
        levels = [dict(row) for row in cur.fetchall()]

        # A parent's contents[] carries the blurb for each of its children.
        cur.execute(
            """
            SELECT DISTINCT
              array_to_string(ARRAY(
                SELECT part FROM jsonb_array_elements_text(taxonomy->'path')
                     WITH ORDINALITY AS t(part, ord)
                WHERE ord <= (l->>'level')::int
              ), ' > ')                      AS parent_path,
              c->>'name'                     AS child_name,
              NULLIF(c->>'note', '')         AS note
            FROM in_use.product_chunks
            CROSS JOIN LATERAL jsonb_array_elements(
              CASE WHEN jsonb_typeof(taxonomy->'levels') = 'array'
                   THEN taxonomy->'levels' ELSE '[]'::jsonb END
            ) AS l
            CROSS JOIN LATERAL jsonb_array_elements(
              CASE WHEN jsonb_typeof(l->'contents') = 'array'
                   THEN l->'contents' ELSE '[]'::jsonb END
            ) AS c
            WHERE is_active
              AND jsonb_typeof(taxonomy->'path') = 'array'
              AND (l->>'level') ~ '^[0-9]+$'
              AND c->>'name' IS NOT NULL
            """
        )
        notes = {
            f"{row['parent_path']} > {row['child_name']}": row["note"]
            for row in cur.fetchall()
            if row["note"]
        }

    rows: dict[str, tuple[Any, ...]] = {}
    described_by_parent = 0
    for level in levels:
        path_text = level["path_text"]
        if not path_text:
            continue
        description = level["description"]
        if not description and (note := notes.get(path_text)):
            description = note
            described_by_parent += 1
        # DISTINCT can yield the same node twice when one source spells a field
        # and another leaves it null; keep the row that says the most.
        existing = rows.get(path_text)
        candidate = (
            path_text,
            level["name"],
            int(level["level"]),
            level["url"],
            description,
            None if level["is_leaf"] is None else int(bool(level["is_leaf"])),
            level["page_type"],
        )
        if existing is None or sum(x is not None for x in candidate) > sum(
            x is not None for x in existing
        ):
            rows[path_text] = candidate

    conn.executemany(
        """
        INSERT INTO taxonomy_level
          (path_text, name, level, url, description, is_leaf, page_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        list(rows.values()),
    )
    conn.commit()
    return {
        "taxonomy_level_rows": len(rows),
        "taxonomy_levels_with_url": sum(1 for r in rows.values() if r[3]),
        "taxonomy_levels_with_description": sum(1 for r in rows.values() if r[4]),
        "taxonomy_descriptions_from_parent": described_by_parent,
    }


def _embedding_blob(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, memoryview):
        return bytes(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if hasattr(value, "to_numpy"):
        import numpy as np

        return np.asarray(value.to_numpy(), dtype=np.float32).tobytes()
    if hasattr(value, "to_list"):
        floats = [float(x) for x in value.to_list()]
        return struct.pack(f"{len(floats)}f", *floats)
    if hasattr(value, "to_binary"):
        return bytes(value.to_binary())
    floats = [float(x) for x in value]
    return struct.pack(f"{len(floats)}f", *floats)


def _insert_chunks(
    conn: sqlite3.Connection, pg, brochure_by_code: dict[str, str | None]
) -> dict[str, Any]:
    level_cols = ",".join(LEVEL_COLUMNS)
    placeholders = ",".join(
        "?"
        for _ in (
            "chunk_id",
            "product_id",
            "sku_code",
            "family",
            *LEVEL_COLUMNS,
            "path_text",
            "chunk_type",
            "headings",
            "content",
            "content_hash",
            "content_len",
            "brochure_md",
            "embedding",
        )
    )
    insert_sql = f"""
        INSERT INTO chunk (
          chunk_id, product_id, sku_code, family, {level_cols},
          path_text, chunk_type, headings, content, content_hash,
          content_len, brochure_md, embedding
        ) VALUES ({placeholders})
    """
    null_embeddings = 0
    total = 0
    batch: list[tuple[Any, ...]] = []
    embedding_dim: int | None = None

    def flush() -> None:
        nonlocal batch
        if batch:
            conn.executemany(insert_sql, batch)
            batch = []

    with pg.cursor(name="chunk_stream") as cur:
        cur.itersize = 1000
        cur.execute(
            """
            SELECT id, product_id, product->>'sku_code' AS sku_code,
                   product->>'family' AS family,
                   taxonomy->'path' AS path,
                   taxonomy->'headings' AS headings,
                   chunk_type, content, embedding
            FROM in_use.product_chunks
            WHERE is_active AND product_id IS NOT NULL
              AND product->>'sku_code' IS NOT NULL
            ORDER BY id
            """
        )
        for row in cur:
            path = _as_path(row.get("path"))
            levels = path_to_levels(path)
            content = row["content"] or ""
            emb = _embedding_blob(row.get("embedding"))
            if emb is None:
                null_embeddings += 1
            elif embedding_dim is None:
                embedding_dim = len(emb) // 4
            pid = int(row["product_id"])
            batch.append(
                (
                    int(row["id"]),
                    pid,
                    row["sku_code"],
                    row.get("family") or NA,
                    *(levels[c] for c in LEVEL_COLUMNS),
                    " > ".join(path),
                    row["chunk_type"],
                    _json_dump(row.get("headings")),
                    content,
                    hashlib.md5(content.encode("utf-8")).hexdigest(),
                    len(content),
                    brochure_by_code.get(row["sku_code"]),
                    emb,
                )
            )
            total += 1
            if len(batch) >= 500:
                flush()
                if total % 10000 == 0:
                    logger.info("chunks inserted: %s", total)
                    conn.commit()
    flush()
    conn.commit()
    return {
        "chunk_rows": total,
        "null_embeddings": null_embeddings,
        "embedding_dim": embedding_dim,
        "embeddings_loaded": null_embeddings < total,
    }


def _create_indexes_and_fts(conn: sqlite3.Connection) -> None:
    logger.info("Creating indexes and FTS5")
    conn.executescript(
        f"""
        CREATE INDEX ix_sf_sku_row ON sku_fact(sku_code, row_id);
        CREATE INDEX ix_sf_spec_value ON sku_fact(spec_id, value_num);
        CREATE INDEX ix_sf_family_spec ON sku_fact(family, spec_id);
        CREATE INDEX ix_sf_family ON sku_fact(family);
        CREATE INDEX ix_sf_levels ON sku_fact(division, product_group, product_subgroup);
        CREATE INDEX ix_sf_value_kind ON sku_fact(value_kind);
        CREATE INDEX ix_sf_price ON sku_fact(price_status);
        CREATE INDEX ix_sf_canonical ON sku_fact(canonical_code);

        CREATE INDEX ix_ch_family_type ON chunk(family, chunk_type);
        CREATE INDEX ix_ch_sku ON chunk(sku_code);
        CREATE INDEX ix_ch_type ON chunk(chunk_type);
        CREATE INDEX ix_ch_hash ON chunk(content_hash);
        CREATE INDEX ix_ch_levels ON chunk(division, product_group, product_subgroup);

        CREATE VIRTUAL TABLE chunk_fts USING fts5(
          content, content='chunk', content_rowid='chunk_id',
          tokenize='porter unicode61'
        );
        INSERT INTO chunk_fts(chunk_fts) VALUES('rebuild');
        """
    )
    conn.commit()


def _write_meta(
    conn: sqlite3.Connection,
    *,
    database_url: str,
    preflight: dict[str, Any],
    sku_stats: dict[str, Any],
    chunk_stats: dict[str, Any],
    taxonomy_stats: dict[str, Any],
    embedding_model: str,
) -> None:
    meta = {
        "source_database": database_url.split("@")[-1] if "@" in database_url else database_url,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "artifact_version": 1,
        "compiled_path_depth": COMPILED_PATH_DEPTH,
        "level_columns": list(LEVEL_COLUMNS),
        "max_observed_path_depth": preflight["max_depth"],
        "mv_counts": {
            "mv_sku": preflight["sku_count"],
            "mv_fact": preflight["fact_count"],
            "product_chunks_active": preflight["chunk_count"],
        },
        "sku_fact_rows": sku_stats["sku_fact_rows"],
        "distinct_skus": sku_stats["distinct_skus"],
        "chunk_rows": chunk_stats["chunk_rows"],
        **taxonomy_stats,
        "embedding_model": embedding_model,
        "embedding_dimension": chunk_stats.get("embedding_dim"),
        "embeddings_loaded": bool(chunk_stats.get("embeddings_loaded")),
        "null_embeddings": chunk_stats["null_embeddings"],
        "factless_sku_count": len(sku_stats["factless_skus"]),
        "no_category_count": sku_stats["no_category_count"],
        "alias_collision_count": len(sku_stats["alias_collisions"]),
        "quotable_sku_count": sku_stats["quotable_skus"],
        "price_sibling_code_count": len(sku_stats["sibling_price_skus"]),
        "composite_count": sum(sku_stats["composite_by_family"].values()),
    }
    conn.execute(
        """
        CREATE TABLE build_meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        "INSERT INTO build_meta(key, value) VALUES (?, ?)",
        [(k, json.dumps(v) if not isinstance(v, str) else v) for k, v in meta.items()],
    )
    # also store full JSON blob
    conn.execute(
        "INSERT INTO build_meta(key, value) VALUES ('full_json', ?)",
        (json.dumps(meta),),
    )
    conn.commit()


def build(output: Path, database_url: str, embedding_model: str) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    for suffix in ("-wal", "-shm"):
        side = Path(str(output) + suffix)
        if side.exists():
            side.unlink()

    logger.info("Connecting to Postgres")
    with _connect_pg(database_url) as pg:
        preflight = _preflight(pg)
        logger.info("Pre-flight: %s", preflight)
        side = _load_side_tables(pg)
        brochure_by_code = {
            code: next(
                (s["ref_name"] for s in rows if s["ref_type"] == "brochure_md"),
                None,
            )
            for code, rows in side[1].items()
        }

        conn = sqlite3.connect(output)
        try:
            _create_schema(conn)
            logger.info("Writing sku_fact")
            sku_stats = _insert_sku_facts(conn, pg, side)
            if sku_stats["factless_skus"]:
                logger.warning(
                    "Factless SKUs (%s): emitting sentinel rows",
                    len(sku_stats["factless_skus"]),
                )
                for item in sku_stats["factless_skus"][:50]:
                    logger.warning("  factless %s | %s | %s", item["sku_code"], item["family"], item["path_text"])
                if len(sku_stats["factless_skus"]) > 50:
                    logger.warning("  ... and %s more", len(sku_stats["factless_skus"]) - 50)
            if sku_stats["alias_collisions"]:
                logger.warning(
                    "Alias collisions: %s codes map to multiple products",
                    len(sku_stats["alias_collisions"]),
                )
            logger.info(
                "Quotable prices: %s SKUs", sku_stats["quotable_skus"]
            )
            if sku_stats["sibling_price_skus"]:
                logger.warning(
                    "Pricelist header names a different code for %s SKUs "
                    "(multi-column binding risk; disclosed as price_sibling_code)",
                    len(sku_stats["sibling_price_skus"]),
                )
            if sku_stats["no_category_count"]:
                logger.warning("SKUs under _no_category: %s", sku_stats["no_category_count"])
            if sku_stats["composite_by_family"]:
                logger.warning(
                    "Composite values: %s facts across %s families",
                    sum(sku_stats["composite_by_family"].values()),
                    len(sku_stats["composite_by_family"]),
                )

            logger.info("Writing taxonomy levels")
            taxonomy_stats = _insert_taxonomy_levels(conn, pg)
            logger.info("Taxonomy levels: %s", taxonomy_stats)

            logger.info("Writing chunks")
            chunk_stats = _insert_chunks(conn, pg, brochure_by_code)
            if chunk_stats["null_embeddings"]:
                logger.warning(
                    "Chunks with NULL embedding: %s (lexical-only until loaded)",
                    chunk_stats["null_embeddings"],
                )

            _create_indexes_and_fts(conn)
            _write_meta(
                conn,
                database_url=database_url,
                preflight=preflight,
                sku_stats=sku_stats,
                chunk_stats=chunk_stats,
                taxonomy_stats=taxonomy_stats,
                embedding_model=embedding_model,
            )
            logger.info("ANALYZE + VACUUM")
            conn.execute("ANALYZE")
            conn.commit()
            conn.execute("VACUUM")
        finally:
            conn.close()

    report = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "output": str(output),
        "preflight": preflight,
        "sku_fact_rows": sku_stats["sku_fact_rows"],
        "distinct_skus": sku_stats["distinct_skus"],
        "chunk_rows": chunk_stats["chunk_rows"],
        **taxonomy_stats,
        "factless_skus": sku_stats["factless_skus"],
        "alias_collisions": sku_stats["alias_collisions"],
        "composite_by_family": sku_stats["composite_by_family"],
        "quotable_skus": sku_stats["quotable_skus"],
        "sibling_price_skus": sku_stats["sibling_price_skus"],
        "no_category_count": sku_stats["no_category_count"],
        "null_embeddings": chunk_stats["null_embeddings"],
        "embeddings_loaded": chunk_stats["embeddings_loaded"],
        "embedding_dim": chunk_stats.get("embedding_dim"),
        "exit_policy": "factless_warn_exit_0",
    }
    report_path = output.parent / "build_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Wrote %s", report_path)

    latest = output.parent / "catalog-latest.sqlite"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    try:
        latest.symlink_to(output.resolve())
    except OSError:
        # fall back to copy on filesystems without symlink support
        import shutil

        shutil.copy2(output, latest)
    logger.info("Linked %s -> %s", latest, output)
    logger.info(
        "Done: %s sku_fact rows, %s chunks, %s distinct SKUs",
        sku_stats["sku_fact_rows"],
        chunk_stats["chunk_rows"],
        sku_stats["distinct_skus"],
    )
    return 0


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / f"catalog-{today}.sqlite",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
    )
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("CS_EMBEDDING_MODEL", "gte_base_en_v1_5"),
    )
    args = parser.parse_args()
    if not args.database_url:
        logger.error("DATABASE_URL is required")
        return 1
    return build(args.output.resolve(), args.database_url, args.embedding_model)


if __name__ == "__main__":
    raise SystemExit(main())
