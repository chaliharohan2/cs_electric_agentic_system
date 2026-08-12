"""PostgreSQL catalogue adapter over the derived ``in_use.mv_*`` views."""

from __future__ import annotations

import os
import re
from typing import Any

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.rows import dict_row

from cs_agent.embeddings import embed


def like_pattern(value: str) -> str:
    """Wrap a user-supplied term for substring ILIKE matching."""
    escaped = (
        str(value)
        .strip()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


class PostgresBackend:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", "")
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is required when CS_BACKEND=postgres")

    def _connect(self):
        connection = psycopg.connect(self.database_url, row_factory=dict_row)
        register_vector(connection)
        return connection

    def list_canonical_specs(self, category: str | None) -> list[dict]:
        query = """
            SELECT spec_id, spec_label, unit, value_kind, sku_count,
                   observed_min, observed_max, category
            FROM in_use.mv_spec_registry
            WHERE (%s::text IS NULL OR category ILIKE %s)
            ORDER BY category, spec_label, spec_id
        """
        pattern = like_pattern(category) if category else None
        with self._connect() as connection:
            return list(connection.execute(query, (category, pattern)).fetchall())

    def taxonomy_browse(
        self, category: str | None = None, family: str | None = None
    ) -> dict:
        with self._connect() as connection:
            if category is None:
                rows = connection.execute(
                    """
                    SELECT category, count(*) AS sku_count
                    FROM in_use.mv_sku GROUP BY category ORDER BY category
                    """
                ).fetchall()
                return {"level": "categories", "categories": list(rows)}
            if family is None:
                rows = connection.execute(
                    """
                    SELECT category, family, count(*) AS sku_count
                    FROM in_use.mv_sku
                    WHERE category ILIKE %s
                    GROUP BY category, family ORDER BY category, family
                    """,
                    (like_pattern(category),),
                ).fetchall()
                return {
                    "level": "families",
                    "category": category,
                    "families": list(rows),
                }
            rows = connection.execute(
                """
                SELECT category, family, axis, code, meaning, sku_count
                FROM in_use.mv_facet
                WHERE category ILIKE %s AND family ILIKE %s
                ORDER BY axis, code
                """,
                (like_pattern(category), like_pattern(family)),
            ).fetchall()
        axes: dict[str, list[dict[str, Any]]] = {}
        matched_families: list[str] = []
        for row in rows:
            item = dict(row)
            axis = item.pop("axis")
            matched = item.pop("family")
            item.pop("category", None)
            if matched not in matched_families:
                matched_families.append(matched)
            axes.setdefault(axis, []).append(item)
        return {
            "level": "facets",
            "category": category,
            "family": family,
            "matched_families": matched_families,
            "sku_count": max(
                (sum(item["sku_count"] for item in values) for values in axes.values()),
                default=0,
            ),
            "axes": axes,
        }

    def product_search(self, **kw: Any) -> list[dict] | dict:
        category = kw.get("category")
        family = kw.get("family")
        facets = kw.get("facets") or {}
        filters = kw.get("filters") or []
        text = kw.get("text")
        return_specs = kw.get("return_specs") or []
        limit = max(1, min(int(kw.get("limit", 20)), 100))

        clauses: list[sql.Composable] = []
        params: list[Any] = []
        if category:
            clauses.append(sql.SQL("s.category ILIKE %s"))
            params.append(like_pattern(category))
        if family:
            clauses.append(sql.SQL("s.family ILIKE %s"))
            params.append(like_pattern(family))
        if text:
            clauses.append(
                sql.SQL(
                    "(s.sku_code ILIKE %s OR s.family ILIKE %s OR s.category ILIKE %s)"
                )
            )
            params.extend([like_pattern(text)] * 3)
        for axis, code in facets.items():
            clauses.append(
                sql.SQL(
                    "EXISTS (SELECT 1 FROM jsonb_each("
                    "CASE WHEN jsonb_typeof(s.decoded) = 'object' "
                    "THEN s.decoded ELSE '{}'::jsonb END) AS d(axis, spec) "
                    "WHERE d.axis ILIKE %s AND ("
                    "d.spec->>'code' ILIKE %s OR d.spec->>'meaning' ILIKE %s))"
                )
            )
            params.extend([like_pattern(axis), like_pattern(code), like_pattern(code)])
        for item in filters:
            spec_id = item["spec_id"]
            operator = item["op"]
            value = item["value"]
            if operator == "gte":
                predicate = sql.SQL("COALESCE(f.value_max, f.value_num) >= %s")
            elif operator == "lte":
                predicate = sql.SQL("COALESCE(f.value_min, f.value_num) <= %s")
            elif operator == "eq":
                predicate = sql.SQL(
                    "%s BETWEEN COALESCE(f.value_min, f.value_num) "
                    "AND COALESCE(f.value_max, f.value_num)"
                )
            elif operator == "contains":
                predicate = sql.SQL("f.value_display ILIKE %s")
                value = f"%{value}%"
            else:
                return {"error": f"Unsupported filter operator: {operator}"}
            clauses.append(
                sql.SQL(
                    "EXISTS (SELECT 1 FROM in_use.mv_fact f "
                    "WHERE f.sku_code = s.sku_code AND f.spec_id ILIKE %s AND "
                )
                + predicate
                + sql.SQL(")")
            )
            params.extend((like_pattern(spec_id), value))

        where = (
            sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses)
            if clauses
            else sql.SQL("")
        )
        query = (
            sql.SQL(
                "SELECT s.sku_code, s.family, s.category, s.decoded AS decoded_summary, "
                "s.completeness, p.value_display AS price_display "
                "FROM in_use.mv_sku s "
                "LEFT JOIN in_use.mv_fact p ON p.sku_code = s.sku_code "
                "AND p.spec_id = 'price_inr'"
            )
            + where
            + sql.SQL(" ORDER BY s.sku_code LIMIT %s")
        )
        params.append(limit)
        with self._connect() as connection:
            hits = [dict(row) for row in connection.execute(query, params).fetchall()]
            if hits and return_specs:
                sku_codes = [hit["sku_code"] for hit in hits]
                facts = connection.execute(
                    """
                    SELECT sku_code, spec_id, spec_label, unit, value_num, value_min,
                           value_max, value_display, value_kind, source_of_truth,
                           derived, fact_sentence
                    FROM in_use.mv_fact
                    WHERE sku_code = ANY(%s)
                      AND spec_id ILIKE ANY(%s)
                    ORDER BY sku_code, spec_id
                    """,
                    (sku_codes, [like_pattern(spec) for spec in return_specs]),
                ).fetchall()
                by_sku: dict[str, list[dict]] = {}
                for fact in facts:
                    by_sku.setdefault(fact["sku_code"], []).append(dict(fact))
                for hit in hits:
                    hit["specs"] = by_sku.get(hit["sku_code"], [])
        return hits

    @staticmethod
    def _match_sku_codes(connection, sku_code: str, limit: int = 10) -> list[str]:
        """Resolve a possibly-partial ordering code, exact matches ranked first."""
        rows = connection.execute(
            """
            SELECT sku_code
            FROM in_use.mv_sku
            WHERE sku_code ILIKE %s
            ORDER BY (lower(sku_code) = lower(%s)) DESC, length(sku_code), sku_code
            LIMIT %s
            """,
            (like_pattern(sku_code), sku_code.strip(), limit),
        ).fetchall()
        return [row["sku_code"] for row in rows]

    def get_sku(self, sku_code: str, include: list[str]) -> dict:
        with self._connect() as connection:
            candidates = self._match_sku_codes(connection, sku_code)
            if not candidates:
                return {"error": f"No SKU matches {sku_code!r}"}
            resolved = candidates[0]
            sku = connection.execute(
                """
                SELECT sku_code, family, category, url, decoded, completeness,
                       sources, has_price, fact_count
                FROM in_use.mv_sku WHERE sku_code = %s
                """,
                (resolved,),
            ).fetchone()
            result = dict(sku)
            if resolved.lower() != sku_code.strip().lower():
                result["requested_sku_code"] = sku_code
                result["other_matches"] = candidates[1:]
            sku_code = resolved
            if "facts" in include:
                result["facts"] = list(
                    connection.execute(
                        """
                        SELECT spec_id, spec_label, unit, value_num, value_min,
                               value_max, value_display, value_kind, source_of_truth,
                               derived, fact_sentence
                        FROM in_use.mv_fact WHERE sku_code = %s ORDER BY spec_id
                        """,
                        (sku_code,),
                    ).fetchall()
                )
            if "content" in include:
                result["content"] = list(
                    connection.execute(
                        """
                        SELECT min(id::text) AS chunk_id, content,
                               min(chunk_type) AS chunk_type,
                               count(*) AS duplicate_count
                        FROM in_use.product_chunks
                        WHERE is_active AND product->>'sku_code' = %s
                        GROUP BY md5(content), content ORDER BY min(id::text)
                        """,
                        (sku_code,),
                    ).fetchall()
                )
            if "decoded" not in include:
                result.pop("decoded", None)
            if "sources" not in include:
                result.pop("sources", None)
        return result

    def compare_skus(
        self, sku_codes: list[str], spec_ids: list[str] | None = None
    ) -> dict:
        spec_patterns = (
            [like_pattern(spec) for spec in spec_ids] if spec_ids else None
        )
        with self._connect() as connection:
            resolved: list[str] = []
            unresolved: list[str] = []
            for requested in sku_codes:
                matches = self._match_sku_codes(connection, requested, limit=1)
                if not matches:
                    unresolved.append(requested)
                elif matches[0] not in resolved:
                    resolved.append(matches[0])
            if not resolved:
                return {
                    "error": f"No SKUs matched {sku_codes!r}",
                    "sku_codes": [],
                    "rows": [],
                }
            sku_codes = resolved
            rows = connection.execute(
                """
                SELECT sku_code, spec_id, spec_label, unit, value_display,
                       value_num, value_min, value_max, value_kind, source_of_truth
                FROM in_use.mv_fact
                WHERE sku_code = ANY(%s)
                  AND (%s::text[] IS NULL OR spec_id ILIKE ANY(%s))
                ORDER BY spec_id, sku_code
                """,
                (sku_codes, spec_patterns, spec_patterns),
            ).fetchall()
        specs: dict[str, dict[str, Any]] = {}
        for raw in rows:
            row = dict(raw)
            spec_id = row["spec_id"]
            entry = specs.setdefault(
                spec_id,
                {
                    "spec_id": spec_id,
                    "spec_label": row["spec_label"],
                    "unit": row["unit"],
                    "values": {code: None for code in sku_codes},
                    "facts": [],
                },
            )
            entry["values"][row["sku_code"]] = row["value_display"]
            entry["facts"].append(row)
        result = {"sku_codes": sku_codes, "rows": list(specs.values())}
        if unresolved:
            result["unresolved_sku_codes"] = unresolved
        return result

    def search_documents(self, **kw: Any) -> list[dict]:
        dimension = self._embedding_dimension()
        vector = Vector(embed(kw["query"], expected_dimension=dimension))
        query = """
            WITH ranked AS (
              SELECT pc.id::text AS chunk_id, pc.content, pc.chunk_type,
                     pc.product->>'sku_code' AS sku_code,
                     pc.product->>'family' AS family,
                     pc.taxonomy->>'category' AS category,
                     pc.embedding <=> %s AS distance,
                     row_number() OVER (
                       PARTITION BY md5(pc.content)
                       ORDER BY pc.embedding <=> %s
                     ) AS rn,
                     count(*) OVER (
                       PARTITION BY md5(pc.content)
                     ) AS shared_by_sku_count
              FROM in_use.product_chunks pc
              WHERE pc.is_active AND pc.embedding IS NOT NULL
                AND (%s::text IS NULL OR pc.taxonomy->>'category' ILIKE %s)
                AND (%s::text IS NULL OR pc.product->>'family' ILIKE %s)
                AND (%s::text IS NULL OR pc.product->>'sku_code' ILIKE %s)
            )
            SELECT chunk_id, content AS text, chunk_type, sku_code, family, category,
                   distance, 1 - distance AS score, shared_by_sku_count
            FROM ranked WHERE rn = 1 ORDER BY distance LIMIT %s
        """
        category, family, sku_code = (
            kw.get("category"),
            kw.get("family"),
            kw.get("sku_code"),
        )
        params = (
            vector,
            vector,
            category,
            like_pattern(category) if category else None,
            family,
            like_pattern(family) if family else None,
            sku_code,
            like_pattern(sku_code) if sku_code else None,
            max(1, min(int(kw.get("k", 6)), 20)),
        )
        with self._connect() as connection:
            return list(connection.execute(query, params).fetchall())

    def _embedding_dimension(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT format_type(a.atttypid, a.atttypmod) AS vector_type
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'in_use' AND c.relname = 'product_chunks'
                  AND a.attname = 'embedding' AND NOT a.attisdropped
                """
            ).fetchone()
        match = re.fullmatch(r"vector\((\d+)\)", row["vector_type"] if row else "")
        if not match:
            raise RuntimeError("Could not determine in_use.product_chunks embedding dimension")
        return int(match.group(1))

    def execute_sql(self, sql: str) -> dict:
        try:
            with self._connect() as connection:
                cursor = connection.execute(sql)
                columns = [column.name for column in cursor.description or []]
                rows = cursor.fetchall() if cursor.description else []
                return {
                    "columns": columns,
                    "rows": [list(row.values()) for row in rows],
                    "row_count": len(rows),
                }
        except psycopg.Error as exc:
            return {"columns": [], "rows": [], "row_count": 0, "error": str(exc)}
