"""Create, refresh, and inspect the catalogue materialized views."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import psycopg
from dotenv import load_dotenv


_VIEWS_SQL = Path(__file__).with_name("views.sql")
_REFRESH_ORDER = (
    "mv_sku",
    "mv_code_alias",
    "mv_fact",
    "mv_price",
    "mv_source",
    "mv_spec_registry",
    "mv_facet",
    "mv_chunk_index",
)


def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required to refresh or inspect the Postgres build source")
    return value


def setup() -> None:
    with psycopg.connect(database_url(), autocommit=True) as connection:
        connection.execute(_VIEWS_SQL.read_text(encoding="utf-8"))


def refresh() -> None:
    with psycopg.connect(database_url(), autocommit=True) as connection:
        for view in _REFRESH_ORDER:
            connection.execute(f"REFRESH MATERIALIZED VIEW in_use.{view}")


def inspect() -> dict[str, object]:
    result: dict[str, object] = {}
    with psycopg.connect(database_url()) as connection:
        base_counts = connection.execute(
            """
            SELECT count(DISTINCT product_id), count(*),
                   count(embedding), count(content_tsv)
            FROM in_use.product_chunks
            WHERE is_active
            """
        ).fetchone()
        result["products"] = int(base_counts[0])
        result["chunks"] = int(base_counts[1])
        result["embeddings_loaded"] = int(base_counts[2])
        result["content_tsv_rows"] = int(base_counts[3])
        for view in _REFRESH_ORDER:
            count = connection.execute(
                f"SELECT count(*) FROM in_use.{view}"
            ).fetchone()
            result[view] = int(count[0])
        type_row = connection.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'in_use'
              AND c.relname = 'product_chunks'
              AND a.attname = 'embedding'
              AND NOT a.attisdropped
            """
        ).fetchone()
        vector_type = type_row[0] if type_row else None
        result["embedding_type"] = vector_type
        match = re.fullmatch(r"vector\((\d+)\)", vector_type or "")
        result["embedding_dimension"] = int(match.group(1)) if match else None
    return result


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("setup", "refresh", "inspect"),
        help="Create views, refresh existing views, or print diagnostics.",
    )
    args = parser.parse_args()
    if args.action == "setup":
        setup()
    elif args.action == "refresh":
        refresh()
    else:
        for key, value in inspect().items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
