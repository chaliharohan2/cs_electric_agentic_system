"""PostgreSQL catalogue adapter over the derived ``in_use.mv_*`` views."""

from __future__ import annotations

import os
import re
from typing import Any

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from cs_agent.embeddings import embed


class PostgresBackend:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", "")
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is required when CS_BACKEND=postgres")

    def _connect(self):
        connection = psycopg.connect(self.database_url, row_factory=dict_row)
        register_vector(connection)
        return connection

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

    @staticmethod
    def _path_clauses(path: list[str] | None, alias: str = "s") -> tuple[list[str], list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for index, part in enumerate(path or []):
            clauses.append(f"{alias}.path->>{index} = %s")
            params.append(part)
        return clauses, params

    @staticmethod
    def _resolved_sku(connection, code: str) -> str | None:
        normalized = re.sub(r"[^a-z0-9]", "", code.lower())
        row = connection.execute(
            """
            SELECT s.sku_code
            FROM in_use.mv_code_alias a
            JOIN in_use.mv_sku s USING (product_id)
            WHERE regexp_replace(lower(a.code), '[^a-z0-9]', '', 'g') = %s
            ORDER BY CASE a.role WHEN 'sku' THEN 0 WHEN 'canonical' THEN 1 ELSE 2 END
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()
        return row["sku_code"] if row else None

    def resolve_product(self, **kw: Any) -> dict:
        query = str(kw["query"]).strip()
        family_hint = kw.get("family_hint")
        limit = max(1, min(int(kw.get("limit", 8)), 20))
        normalized = re.sub(r"[^a-z0-9]", "", query.lower())
        family_clause = "AND s.family ILIKE %s" if family_hint else ""
        family_params = [f"%{family_hint}%"] if family_hint else []
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT s.sku_code, s.canonical_code, s.family, s.path_text,
                       a.role AS match_role, 1.0::float AS score, s.description,
                       s.alias_reason
                FROM in_use.mv_code_alias a
                JOIN in_use.mv_sku s USING (product_id)
                WHERE regexp_replace(lower(a.code), '[^a-z0-9]', '', 'g') = %s
                  {family_clause}
                ORDER BY CASE a.role WHEN 'sku' THEN 0 WHEN 'canonical' THEN 1 ELSE 2 END
                LIMIT %s
                """,
                [normalized, *family_params, limit],
            ).fetchall()
            resolution = "exact"
            if not rows:
                rows = connection.execute(
                    f"""
                    SELECT s.sku_code, s.canonical_code, s.family, s.path_text,
                           a.role AS match_role, similarity(a.code, %s) AS score,
                           s.description, s.alias_reason
                    FROM in_use.mv_code_alias a
                    JOIN in_use.mv_sku s USING (product_id)
                    WHERE similarity(a.code, %s) >= 0.35 {family_clause}
                    ORDER BY score DESC, length(a.code), s.sku_code
                    LIMIT %s
                    """,
                    [query, query, *family_params, limit],
                ).fetchall()
                resolution = "fuzzy"
            if not rows:
                rows = connection.execute(
                    f"""
                    SELECT DISTINCT ON (s.product_id)
                           s.sku_code, s.canonical_code, s.family, s.path_text,
                           'description'::text AS match_role,
                           greatest(similarity(COALESCE(s.description,''), %s),
                                    similarity(COALESCE(s.family,''), %s)) AS score,
                           s.description, s.alias_reason
                    FROM in_use.mv_sku s
                    LEFT JOIN in_use.product_chunks pc
                      ON pc.product_id = s.product_id AND pc.is_active
                    WHERE (
                      similarity(COALESCE(s.description,''), %s) >= 0.2
                      OR similarity(COALESCE(s.family,''), %s) >= 0.2
                      OR pc.content_tsv @@ plainto_tsquery('english', %s)
                    ) {family_clause}
                    ORDER BY s.product_id, score DESC
                    LIMIT %s
                    """,
                    [query, query, query, query, query, *family_params, limit],
                ).fetchall()
                resolution = "descriptive"
        hits = [dict(row) for row in rows]
        result: dict[str, Any] = {"resolution": resolution, "hits": hits}
        alias_hits = [hit for hit in hits if hit["match_role"] == "alias"]
        if alias_hits:
            result["alias_note"] = alias_hits[0].get("alias_reason") or (
                "The supplied code is an alternate published spelling."
            )
        return result

    def list_canonical_specs(self, **kw: Any) -> list[dict]:
        clauses = ["TRUE"]
        params: list[Any] = []
        if family := kw.get("family"):
            clauses.append("family ILIKE %s")
            params.append(f"%{family}%")
        if contains := kw.get("spec_id_contains"):
            clauses.append("(spec_id ILIKE %s OR spec_label ILIKE %s)")
            params.extend([f"%{contains}%", f"%{contains}%"])
        if kw.get("canonical_only"):
            clauses.append("is_canonical_spec")
        with self._connect() as connection:
            return list(
                connection.execute(
                    f"""
                    SELECT family, spec_id, spec_label, unit, value_kind,
                           is_canonical_spec, sku_count, composite_count,
                           observed_min, observed_max
                    FROM in_use.mv_spec_registry
                    WHERE {' AND '.join(clauses)}
                    ORDER BY family, spec_label, spec_id
                    """,
                    params,
                ).fetchall()
            )

    def taxonomy_browse(self, **kw: Any) -> dict:
        path = kw.get("path") or []
        clauses, params = self._path_clauses(path)
        if segment := kw.get("market_segment"):
            clauses.append("s.market_segments::text ILIKE %s")
            params.append(f"%{segment}%")
        where = " AND ".join(clauses) if clauses else "TRUE"
        depth = len(path)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                WITH children AS (
                  SELECT s.path->>{depth} AS name,
                         count(*) AS sku_count,
                         bool_and(s.depth = {depth} + 1) AS is_leaf,
                         min(s.product_id) AS sample_product_id
                  FROM in_use.mv_sku s
                  WHERE {where} AND jsonb_array_length(s.path) > {depth}
                  GROUP BY s.path->>{depth}
                )
                SELECT c.name, c.sku_count, c.is_leaf,
                       COALESCE(
                         lvl->>'description',
                         lvl->>'note',
                         lvl->>'name'
                       ) AS description,
                       lvl->>'url' AS url
                FROM children c
                LEFT JOIN LATERAL (
                  SELECT pc.taxonomy->'levels'->{depth} AS lvl
                  FROM in_use.product_chunks pc
                  WHERE pc.product_id = c.sample_product_id AND pc.is_active
                  ORDER BY pc.id
                  LIMIT 1
                ) meta ON TRUE
                ORDER BY c.name
                """,
                params,
            ).fetchall()
            normal = [dict(row) for row in rows if row["name"] != "_no_category"]
            uncategorised = [dict(row) for row in rows if row["name"] == "_no_category"]
            result: dict[str, Any] = {
                "path": path,
                "children": normal,
                "uncategorised": {
                    "children": uncategorised,
                    "note": (
                        "These are pricelist section names, not published C&S categories."
                    ),
                },
            }
            if kw.get("include_facets") and path:
                leaf_family = path[-1]
                result["facets"] = list(
                    connection.execute(
                        """
                        SELECT axis, code, meaning, sku_count
                        FROM in_use.mv_facet
                        WHERE family = %s ORDER BY axis, code, meaning
                        """,
                        (leaf_family,),
                    ).fetchall()
                )
        return result

    def product_search(self, **kw: Any) -> dict:
        clauses, params = self._path_clauses(kw.get("path"))
        filters = kw.get("filters") or []
        if family := kw.get("family"):
            clauses.append("s.family ILIKE %s")
            params.append(f"%{family}%")
        if text := kw.get("text"):
            clauses.append(
                "(s.sku_code ILIKE %s OR s.canonical_code ILIKE %s "
                "OR s.family ILIKE %s OR s.description ILIKE %s)"
            )
            params.extend([f"%{text}%"] * 4)
        if segment := kw.get("market_segment"):
            clauses.append("s.market_segments::text ILIKE %s")
            params.append(f"%{segment}%")
        if statuses := kw.get("price_status"):
            clauses.append("s.price_status = ANY(%s)")
            params.append(statuses)
        if chunk_types := kw.get("has_chunk_type"):
            clauses.append(
                "EXISTS (SELECT 1 FROM in_use.mv_chunk_index ci "
                "WHERE ci.product_id=s.product_id AND ci.chunk_type = ANY(%s))"
            )
            params.append(chunk_types)
        for axis, code in (kw.get("facets") or {}).items():
            clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_each(CASE WHEN jsonb_typeof(s.decoded)='object' "
                "THEN s.decoded ELSE '{}'::jsonb END) d(axis,spec) "
                "WHERE d.axis ILIKE %s AND "
                "(d.spec->>'code' ILIKE %s OR d.spec->>'meaning' ILIKE %s))"
            )
            params.extend([axis, code, code])
        numeric_spec_ids: list[str] = []
        applied: list[str] = []
        for item in filters:
            spec_id, operator, value = item["spec_id"], item["op"], item["value"]
            if operator == "gte":
                predicate = "COALESCE(f.value_max,f.value_num) >= %s"
                numeric_spec_ids.append(spec_id)
            elif operator == "lte":
                predicate = "COALESCE(f.value_min,f.value_num) <= %s"
                numeric_spec_ids.append(spec_id)
            elif operator == "eq":
                predicate = "%s BETWEEN COALESCE(f.value_min,f.value_num) AND COALESCE(f.value_max,f.value_num)"
                numeric_spec_ids.append(spec_id)
            elif operator == "contains":
                predicate = "f.value_display ILIKE %s"
                value = f"%{value}%"
            else:
                return {"error": f"Unsupported filter operator: {operator}"}
            clauses.append(
                "EXISTS (SELECT 1 FROM in_use.mv_fact f WHERE f.product_id=s.product_id "
                "AND f.spec_id=%s AND " + predicate + ")"
            )
            params.extend([spec_id, value])
            applied.append(f"{spec_id} {operator} {item['value']}")
        where = " AND ".join(clauses) if clauses else "TRUE"
        return_specs = kw.get("return_specs") or []
        limit = max(1, min(int(kw.get("limit", 20)), 100))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT s.product_id, s.sku_code, s.canonical_code, s.family,
                       s.path, s.description, s.url, s.price_status, s.decoded,
                       count(*) OVER() AS total_matched
                FROM in_use.mv_sku s
                WHERE {where}
                ORDER BY s.sku_code LIMIT %s
                """,
                [*params, limit],
            ).fetchall()
            hits = [dict(row) for row in rows]
            total = int(hits[0].pop("total_matched")) if hits else 0
            for hit in hits[1:]:
                hit.pop("total_matched", None)
            if hits and return_specs:
                facts = connection.execute(
                    """
                    SELECT product_id, spec_id, spec_label, unit, value_num, value_min,
                           value_max, value_display, value_kind, source_of_truth,
                           source_pdf, source_page
                    FROM in_use.mv_fact
                    WHERE product_id = ANY(%s) AND spec_id = ANY(%s)
                    ORDER BY product_id, spec_id
                    """,
                    [[hit["product_id"] for hit in hits], return_specs],
                ).fetchall()
                by_product: dict[int, list[dict]] = {}
                for fact in facts:
                    by_product.setdefault(fact["product_id"], []).append(dict(fact))
                for hit in hits:
                    hit["specs"] = by_product.get(hit["product_id"], [])
            composite_excluded = 0
            if numeric_spec_ids:
                base_clauses, base_params = self._path_clauses(kw.get("path"))
                if family:
                    base_clauses.append("s.family ILIKE %s")
                    base_params.append(f"%{family}%")
                row = connection.execute(
                    f"""
                    SELECT count(DISTINCT s.product_id) AS n
                    FROM in_use.mv_sku s
                    JOIN in_use.mv_fact f ON f.product_id=s.product_id
                    WHERE {' AND '.join(base_clauses) if base_clauses else 'TRUE'}
                      AND f.spec_id = ANY(%s) AND f.value_kind='composite'
                    """,
                    [*base_params, numeric_spec_ids],
                ).fetchone()
                composite_excluded = int(row["n"])
        return {
            "hits": hits,
            "total_matched": total,
            "composite_excluded": composite_excluded,
            "filters_applied": applied,
            "widening_hint": (
                None if total else (
                    f"Relax {applied[-1]}" if applied else "Broaden the path, family, or text filter."
                )
            ),
        }

    def get_sku(self, sku_code: str, include: list[str], **kw: Any) -> dict:
        with self._connect() as connection:
            resolved = self._resolved_sku(connection, sku_code)
            if not resolved:
                return {"error": f"No ordering code resolves from {sku_code!r}"}
            row = connection.execute(
                """
                SELECT product_id, sku_code, canonical_code, family, description, url,
                       price_status, peer_group, path, headings, decoded, attributes,
                       comparable_on, related_codes, also_published_as, alias_reason,
                       extraction_missing, extraction_confidence, fact_count
                FROM in_use.mv_sku WHERE sku_code=%s
                """,
                (resolved,),
            ).fetchone()
            result = dict(row)
            result["extraction"] = {
                "missing": result.pop("extraction_missing"),
                "confidence": result.pop("extraction_confidence"),
            }
            if "facts" in include:
                result["facts"] = list(connection.execute(
                    """
                    SELECT spec_id, spec_label, unit, is_canonical_spec, value_num,
                           value_min, value_max, value_display, value_kind,
                           source_of_truth, source_pdf, source_page, source_heading,
                           fact_sentence
                    FROM in_use.mv_fact WHERE product_id=%s ORDER BY spec_id
                    """, (row["product_id"],)
                ).fetchall())
            if "sources" in include:
                result["sources"] = list(connection.execute(
                    "SELECT ref_type, ref_name, page FROM in_use.mv_source "
                    "WHERE product_id=%s ORDER BY ref_type, ref_name",
                    (row["product_id"],),
                ).fetchall())
            if "chunks" in include:
                chunk_types = kw.get("chunk_types")
                result["chunks"] = list(connection.execute(
                    """
                    SELECT min(id)::text AS chunk_id, content AS text,
                           min(chunk_type) AS chunk_type,
                           jsonb_agg(taxonomy->'headings')->0 AS headings,
                           count(*) AS duplicate_count
                    FROM in_use.product_chunks
                    WHERE is_active AND product_id=%s
                      AND (%s::text[] IS NULL OR chunk_type=ANY(%s))
                    GROUP BY md5(content), content ORDER BY min(id)
                    """, (row["product_id"], chunk_types, chunk_types)
                ).fetchall())
            if "decoded" not in include:
                result.pop("decoded", None)
        if "price" in include:
            result["price"] = self.get_price_detail([resolved])["prices"][0]
        if "peers" in include:
            result["peers"] = self.get_peer_group(resolved)
        return result

    def get_price_detail(self, sku_codes: list[str]) -> dict:
        prices: list[dict[str, Any]] = []
        with self._connect() as connection:
            for requested in sku_codes:
                resolved = self._resolved_sku(connection, requested)
                if not resolved:
                    prices.append({"sku_code": requested, "error": "unresolved"})
                    continue
                sku = connection.execute(
                    "SELECT product_id, sku_code, price_status FROM in_use.mv_sku WHERE sku_code=%s",
                    (resolved,),
                ).fetchone()
                observations = [dict(row) for row in connection.execute(
                    """
                    SELECT price, price_list, source_pdf, source_page, effective_date,
                           observation_status, context, context_names_own_code
                    FROM in_use.mv_price WHERE product_id=%s ORDER BY source_pdf, source_page
                    """, (sku["product_id"],)
                ).fetchall()]
                prices.append({
                    "sku_code": resolved,
                    "price_status": sku["price_status"],
                    "observations": observations,
                    "quotable": (
                        sku["price_status"] != "multiple_variants"
                        and bool(observations)
                        and any(item["context_names_own_code"] for item in observations)
                    ),
                })
        return {"prices": prices}

    def get_peer_group(self, sku_code: str) -> dict:
        with self._connect() as connection:
            resolved = self._resolved_sku(connection, sku_code)
            if not resolved:
                return {"error": f"No ordering code resolves from {sku_code!r}"}
            anchor = connection.execute(
                "SELECT peer_group, comparable_on, related_codes FROM in_use.mv_sku WHERE sku_code=%s",
                (resolved,),
            ).fetchone()
            if not anchor["peer_group"]:
                return {
                    "sku_code": resolved,
                    "peer_group": None,
                    "comparable_on": anchor["comparable_on"] or [],
                    "related_codes": anchor["related_codes"] or [],
                    "peers": [],
                }
            peers = connection.execute(
                """
                SELECT sku_code, family, decoded, price_status
                FROM in_use.mv_sku WHERE peer_group=%s ORDER BY sku_code
                """, (anchor["peer_group"],)
            ).fetchall()
        return {
            "sku_code": resolved,
            "peer_group": anchor["peer_group"],
            "comparable_on": anchor["comparable_on"] or [],
            "related_codes": anchor["related_codes"] or [],
            "peers": list(peers),
        }

    def compare_skus(
        self, sku_codes: list[str], spec_ids: list[str] | None = None
    ) -> dict:
        with self._connect() as connection:
            resolved = [self._resolved_sku(connection, code) for code in sku_codes]
            unresolved = [
                code for code, match in zip(sku_codes, resolved, strict=True) if not match
            ]
            codes = list(dict.fromkeys(code for code in resolved if code))
            if not codes:
                return {"error": "No supplied ordering code resolved", "unresolved_sku_codes": unresolved}
            metadata = list(connection.execute(
                "SELECT sku_code, peer_group, comparable_on FROM in_use.mv_sku "
                "WHERE sku_code=ANY(%s)", (codes,)
            ).fetchall())
            groups = {row["peer_group"] for row in metadata if row["peer_group"]}
            peer_match = len(groups) == 1 and len(metadata) == len(codes)
            axes_source = "union"
            axes = spec_ids
            if not axes and peer_match:
                sets = [set(row["comparable_on"] or []) for row in metadata]
                axes = sorted(set.intersection(*sets)) if sets else []
                axes_source = "comparable_on"
            if not axes:
                axes = [row["spec_id"] for row in connection.execute(
                    "SELECT DISTINCT spec_id FROM in_use.mv_fact "
                    "WHERE sku_code=ANY(%s) ORDER BY spec_id", (codes,)
                ).fetchall()]
            facts = connection.execute(
                """
                SELECT sku_code, spec_id, value_display
                FROM in_use.mv_fact WHERE sku_code=ANY(%s) AND spec_id=ANY(%s)
                """, (codes, axes)
            ).fetchall()
        rows = {
            axis: {code: None for code in codes}
            for axis in axes
        }
        for fact in facts:
            rows[fact["spec_id"]][fact["sku_code"]] = fact["value_display"]
        return {
            "sku_codes": codes,
            "axes": axes,
            "rows": rows,
            "peer_group_match": peer_match,
            "axes_source": axes_source,
            "unresolved_sku_codes": unresolved,
        }

    @staticmethod
    def _document_filters(kw: dict[str, Any]) -> tuple[list[str], list[Any]]:
        clauses = ["pc.is_active"]
        params: list[Any] = []
        for index, part in enumerate(kw.get("path") or []):
            clauses.append(f"pc.taxonomy->'path'->>{index} = %s")
            params.append(part)
        if family := kw.get("family"):
            clauses.append("pc.product->>'family' ILIKE %s")
            params.append(f"%{family}%")
        if sku_code := kw.get("sku_code"):
            clauses.append("pc.product->>'sku_code' = %s")
            params.append(sku_code)
        if chunk_types := kw.get("chunk_types"):
            clauses.append("pc.chunk_type = ANY(%s)")
            params.append(chunk_types)
        return clauses, params

    def search_documents(self, **kw: Any) -> list[dict]:
        if not kw.get("path") and not kw.get("family"):
            return [{
                "error": "search_documents requires at least one path or family filter",
                "mode": "none",
            }]
        clauses, filter_params = self._document_filters(kw)
        limit = max(1, min(int(kw.get("k", 6)), 20))
        with self._connect() as connection:
            available = connection.execute(
                f"""
                SELECT EXISTS(
                  SELECT 1 FROM in_use.product_chunks pc
                  WHERE {' AND '.join(clauses)} AND pc.embedding IS NOT NULL
                ) AS present
                """,
                filter_params,
            ).fetchone()["present"]
            if available:
                dimension = self._embedding_dimension()
                vector = Vector(embed(kw["query"], expected_dimension=dimension))
                rows = connection.execute(
                    f"""
                    WITH ranked AS (
                      SELECT pc.id::text AS chunk_id, pc.product_id,
                             pc.content AS text, pc.chunk_type,
                             pc.taxonomy->'headings' AS headings,
                             pc.product->>'sku_code' AS sku_code,
                             pc.product->>'family' AS family,
                             pc.embedding <=> %s AS distance,
                             row_number() OVER (
                               PARTITION BY md5(pc.content)
                               ORDER BY pc.embedding <=> %s
                             ) AS rn,
                             count(*) OVER (
                               PARTITION BY md5(pc.content)
                             ) AS shared_by_sku_count
                      FROM in_use.product_chunks pc
                      WHERE {' AND '.join(clauses)}
                        AND pc.embedding IS NOT NULL
                    )
                    SELECT r.chunk_id, r.text, r.chunk_type, r.headings, r.sku_code,
                           r.family, r.distance, 1-r.distance AS score,
                           r.shared_by_sku_count,
                           (
                             SELECT src.ref_name FROM in_use.mv_source src
                             WHERE src.product_id=r.product_id
                               AND src.ref_type='brochure_md'
                             ORDER BY src.ref_name LIMIT 1
                           ) AS brochure_md,
                           'vector'::text AS mode
                    FROM ranked r WHERE r.rn=1
                    ORDER BY r.distance LIMIT %s
                    """,
                    [vector, vector, *filter_params, limit],
                ).fetchall()
                if rows:
                    return list(rows)
            rows = connection.execute(
                f"""
                WITH ranked AS (
                  SELECT pc.id::text AS chunk_id, pc.product_id,
                         pc.content AS text, pc.chunk_type,
                         pc.taxonomy->'headings' AS headings,
                         pc.product->>'sku_code' AS sku_code,
                         pc.product->>'family' AS family,
                         ts_rank_cd(pc.content_tsv, plainto_tsquery('english', %s)) AS score,
                         row_number() OVER (
                           PARTITION BY md5(pc.content)
                           ORDER BY ts_rank_cd(
                             pc.content_tsv, plainto_tsquery('english', %s)
                           ) DESC
                         ) AS rn,
                         count(*) OVER (
                           PARTITION BY md5(pc.content)
                         ) AS shared_by_sku_count
                  FROM in_use.product_chunks pc
                  WHERE {' AND '.join(clauses)}
                    AND pc.content_tsv @@ plainto_tsquery('english', %s)
                )
                SELECT r.chunk_id, r.text, r.chunk_type, r.headings, r.sku_code,
                       r.family, r.score, r.shared_by_sku_count,
                       (
                         SELECT src.ref_name FROM in_use.mv_source src
                         WHERE src.product_id=r.product_id
                           AND src.ref_type='brochure_md'
                         ORDER BY src.ref_name LIMIT 1
                       ) AS brochure_md,
                       'lexical'::text AS mode
                FROM ranked r WHERE r.rn=1
                ORDER BY r.score DESC LIMIT %s
                """,
                [kw["query"], kw["query"], *filter_params, kw["query"], limit],
            ).fetchall()
        return list(rows)

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
