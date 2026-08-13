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

from cs_agent.backends.matching import (
    any_term_predicate,
    distinctive_words,
    normalized_sql,
    text_predicate,
)
from cs_agent.embeddings import embed

SPEC_NAME_COLUMNS = ("spec_id", "spec_label")


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
        clause, params = (
            text_predicate(("category",), category) if category else ("TRUE", [])
        )
        query = f"""
            SELECT spec_id, spec_label, unit, value_kind, sku_count,
                   observed_min, observed_max, category
            FROM in_use.mv_spec_registry
            WHERE {clause}
            ORDER BY category, spec_label, spec_id
        """
        with self._connect() as connection:
            return list(connection.execute(query, params).fetchall())

    def taxonomy_browse(
        self, category: str | None = None, family: str | None = None
    ) -> dict:
        with self._connect() as connection:
            if family is not None:
                return self._facets(connection, category, family)
            if category is None:
                rows = connection.execute(
                    """
                    SELECT category, count(*) AS sku_count
                    FROM in_use.mv_sku GROUP BY category ORDER BY category
                    """
                ).fetchall()
                return {"level": "categories", "categories": list(rows)}
            clause, params = text_predicate(("category",), category)
            rows = connection.execute(
                f"""
                SELECT category, family, count(*) AS sku_count
                FROM in_use.mv_sku
                WHERE {clause}
                GROUP BY category, family ORDER BY category, family
                """,
                params,
            ).fetchall()
        return {
            "level": "families",
            "category": category,
            "families": list(rows),
        }

    def _facets(self, connection, category: str | None, family: str) -> dict:
        """Ordering-code axes for the matching families.

        ``category`` is optional: a family or product-line name is often all the
        caller knows, and silently ignoring it would return the whole catalogue.
        """
        clause, params = text_predicate(("family",), family)
        if category:
            category_clause, category_params = text_predicate(("category",), category)
            clause = f"{clause} AND {category_clause}"
            params = params + category_params
        rows = connection.execute(
            f"""
            SELECT category, family, axis, code, meaning, sku_count
            FROM in_use.mv_facet
            WHERE {clause}
            ORDER BY category, family, axis, code
            """,
            params,
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
        result = {
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
        if not matched_families:
            result["no_matches"] = (
                f"No family matches {family!r}"
                + (f" within category {category!r}" if category else "")
            )
            result["suggestions"] = self._name_suggestions(connection, family)
        return result

    @staticmethod
    def _name_suggestions(connection, term: str) -> dict[str, list[str]]:
        """Catalogue names sharing a word with ``term``, to unstick a bad guess."""
        words = distinctive_words(term)
        if not words:
            return {"categories": [], "families": []}
        clause, params = any_term_predicate(("category", "family"), words)
        rows = connection.execute(
            f"""
            SELECT DISTINCT category, family FROM in_use.mv_sku
            WHERE {clause} ORDER BY category, family LIMIT 15
            """,
            params,
        ).fetchall()
        return {
            "categories": sorted({row["category"] for row in rows}),
            "families": sorted({row["family"] for row in rows}),
        }

    def product_search(self, **kw: Any) -> list[dict] | dict:
        category = kw.get("category")
        family = kw.get("family")
        facets = kw.get("facets") or {}
        filters = kw.get("filters") or []
        text = kw.get("text")
        return_specs = kw.get("return_specs") or []
        limit = max(1, min(int(kw.get("limit", 20)), 100))

        # Name and narrowing clauses are tracked apart so an empty result can say
        # whether the name was unknown or the filters were too tight.
        name_clauses: list[sql.Composable] = []
        name_params: list[Any] = []
        clauses: list[sql.Composable] = []
        params: list[Any] = []

        def add_name(fragment: str, fragment_params: list[Any]) -> None:
            name_clauses.append(sql.SQL(fragment))
            name_params.extend(fragment_params)

        def add(fragment: str, fragment_params: list[Any]) -> None:
            clauses.append(sql.SQL(fragment))
            params.extend(fragment_params)

        if category:
            add_name(*text_predicate(("s.category",), category))
        if family:
            add_name(*text_predicate(("s.family",), family))
        if text:
            add_name(*text_predicate(("s.sku_code", "s.family", "s.category"), text))
        for axis, code in facets.items():
            axis_clause, axis_params = text_predicate(("d.axis",), axis)
            code_clause, code_params = text_predicate(
                ("d.spec->>'code'", "d.spec->>'meaning'"), code
            )
            add(
                "EXISTS (SELECT 1 FROM jsonb_each("
                "CASE WHEN jsonb_typeof(s.decoded) = 'object' "
                "THEN s.decoded ELSE '{}'::jsonb END) AS d(axis, spec) "
                f"WHERE {axis_clause} AND {code_clause})",
                axis_params + code_params,
            )
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
            spec_clause, spec_params = text_predicate(
                tuple(f"f.{column}" for column in SPEC_NAME_COLUMNS), spec_id
            )
            clauses.append(
                sql.SQL(
                    "EXISTS (SELECT 1 FROM in_use.mv_fact f "
                    f"WHERE f.sku_code = s.sku_code AND {spec_clause} AND "
                )
                + predicate
                + sql.SQL(")")
            )
            params.extend(spec_params)
            params.append(value)

        all_clauses = name_clauses + clauses
        all_params = name_params + params
        where = (
            sql.SQL(" WHERE ") + sql.SQL(" AND ").join(all_clauses)
            if all_clauses
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
        with self._connect() as connection:
            hits = [
                dict(row)
                for row in connection.execute(query, [*all_params, limit]).fetchall()
            ]
            if not hits:
                return self._no_search_matches(
                    connection,
                    term=next(
                        (value for value in (category, family, text) if value), None
                    ),
                    name_clauses=name_clauses,
                    name_params=name_params,
                    narrowed=bool(clauses),
                )
            if return_specs:
                sku_codes = [hit["sku_code"] for hit in hits]
                spec_clause, spec_params = any_term_predicate(
                    SPEC_NAME_COLUMNS, return_specs
                )
                facts = connection.execute(
                    f"""
                    SELECT sku_code, spec_id, spec_label, unit, value_num, value_min,
                           value_max, value_display, value_kind, source_of_truth,
                           derived, fact_sentence
                    FROM in_use.mv_fact
                    WHERE sku_code = ANY(%s) AND {spec_clause}
                    ORDER BY sku_code, spec_id
                    """,
                    [sku_codes, *spec_params],
                ).fetchall()
                by_sku: dict[str, list[dict]] = {}
                for fact in facts:
                    by_sku.setdefault(fact["sku_code"], []).append(dict(fact))
                for hit in hits:
                    hit["specs"] = by_sku.get(hit["sku_code"], [])
        return hits

    def _no_search_matches(
        self,
        connection,
        *,
        term: str | None,
        name_clauses: list[sql.Composable],
        name_params: list[Any],
        narrowed: bool,
    ) -> list[dict] | dict:
        """Explain an empty result: unknown name, or filters that excluded everything."""
        if term is None:
            return []
        if narrowed and name_clauses:
            named = connection.execute(
                sql.SQL("SELECT count(*) AS total FROM in_use.mv_sku s WHERE ")
                + sql.SQL(" AND ").join(name_clauses),
                name_params,
            ).fetchone()
            if named and named["total"]:
                return {
                    "hits": [],
                    "no_matches": (
                        f"{term!r} matches {named['total']} SKUs, but none satisfy the "
                        "filters and facets given. Check the observed_min and "
                        "observed_max from list_canonical_specs and relax them."
                    ),
                }
        suggestions = self._name_suggestions(connection, term)
        if not suggestions["categories"] and not suggestions["families"]:
            return []
        return {
            "hits": [],
            "no_matches": (
                f"No SKU matched. The catalogue has no name matching {term!r}, but "
                "the names below share a word with it. Retry with one of them."
            ),
            "suggestions": suggestions,
        }

    @staticmethod
    def _match_sku_codes(connection, sku_code: str, limit: int = 10) -> list[str]:
        """Resolve a possibly-partial ordering code, exact matches ranked first."""
        clause, params = text_predicate(("sku_code",), sku_code)
        normalized = normalized_sql("sku_code")
        rows = connection.execute(
            f"""
            SELECT sku_code
            FROM in_use.mv_sku
            WHERE {clause}
            ORDER BY ({normalized} = {normalized_sql('%s::text')}) DESC,
                     length(sku_code), sku_code
            LIMIT %s
            """,
            [*params, str(sku_code).strip(), limit],
        ).fetchall()
        return [row["sku_code"] for row in rows]

    def get_sku(self, sku_code: str, include: list[str]) -> dict:
        with self._connect() as connection:
            candidates = self._match_sku_codes(connection, sku_code)
            if not candidates:
                return {
                    "error": f"No ordering code matches {sku_code!r}",
                    "suggestions": self._name_suggestions(connection, sku_code),
                }
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
        spec_clause, spec_params = (
            any_term_predicate(SPEC_NAME_COLUMNS, spec_ids)
            if spec_ids
            else ("TRUE", [])
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
                    "error": (
                        f"No ordering code matches {sku_codes!r}. compare_skus takes "
                        "ordering codes, not family or product-line names; use "
                        "product_search to turn a name into ordering codes first."
                    ),
                    "sku_codes": [],
                    "rows": [],
                    "suggestions": {
                        requested: self._name_suggestions(connection, requested)
                        for requested in unresolved
                    },
                }
            sku_codes = resolved
            rows = connection.execute(
                f"""
                SELECT sku_code, spec_id, spec_label, unit, value_display,
                       value_num, value_min, value_max, value_kind, source_of_truth
                FROM in_use.mv_fact
                WHERE sku_code = ANY(%s) AND {spec_clause}
                ORDER BY spec_id, sku_code
                """,
                [sku_codes, *spec_params],
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
        filters = [
            ("pc.taxonomy->>'category'", kw.get("category")),
            ("pc.product->>'family'", kw.get("family")),
            ("pc.product->>'sku_code'", kw.get("sku_code")),
        ]
        clauses = ["pc.is_active", "pc.embedding IS NOT NULL"]
        params: list[Any] = [vector, vector]
        for expression, wanted in filters:
            if not wanted:
                continue
            clause, clause_params = text_predicate((expression,), wanted)
            clauses.append(clause)
            params.extend(clause_params)
        params.append(max(1, min(int(kw.get("k", 6)), 20)))
        query = f"""
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
              WHERE {" AND ".join(clauses)}
            )
            SELECT chunk_id, content AS text, chunk_type, sku_code, family, category,
                   distance, 1 - distance AS score, shared_by_sku_count
            FROM ranked WHERE rn = 1 ORDER BY distance LIMIT %s
        """
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
