"""SQLite catalogue adapter over the built ``sku_fact`` / ``chunk`` artifact."""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import struct
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz, process

from cs_agent.backends.path_levels import LEVEL_COLUMNS, NA
from cs_agent.backends.vec_support import try_load_sqlite_vec
from cs_agent.config.limits import get_limits
from cs_agent.embeddings import embed

logger = logging.getLogger(__name__)

_SKU_GRAIN = (
    "row_id IN (SELECT min(row_id) FROM sku_fact GROUP BY sku_code)"
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = _project_root() / path
    return path


def _loads(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default if default is not None else value
    return value


def _normalize_code(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _fts_query(value: str) -> str:
    """Turn free text into a safe FTS5 MATCH query (no column operators)."""
    tokens = re.findall(r"[A-Za-z0-9_]+", value)
    return " ".join(tokens)


def _serialize_vec(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *[float(x) for x in vector])


class SqliteBackend:
    def __init__(self, sqlite_path: str | Path | None = None) -> None:
        limits = get_limits()
        raw = sqlite_path or os.getenv("CS_SQLITE_PATH") or limits.sqlite_path
        self.sqlite_path = _resolve_path(str(raw))
        if not self.sqlite_path.exists():
            raise RuntimeError(
                f"SQLite catalogue not found at {self.sqlite_path}. "
                "Run: python scripts/build_sqlite.py"
            )
        self._pragmas = dict(limits.sqlite_pragmas)
        self._local = threading.local()
        self._alias_lock = threading.Lock()
        self._alias_entries: list[tuple[str, str, str]] | None = None
        self._alias_norm: dict[str, list[tuple[str, str]]] | None = None
        self.vec_available = self._probe_vec()
        if not self.vec_available:
            logger.warning(
                "sqlite-vec unavailable; search_documents will use FTS5 lexical search"
            )
        self._assert_embedding_dim()

    def _probe_vec(self) -> bool:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            return try_load_sqlite_vec(connection)
        finally:
            connection.close()

    def _meta(self, key: str) -> Any:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM build_meta WHERE key = ?", (key,)
            ).fetchone()
        if not row:
            return None
        value = row["value"]
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value

    def _assert_embedding_dim(self) -> None:
        if not self._meta("embeddings_loaded"):
            return
        stored = self._meta("embedding_dimension")
        if not stored:
            return
        # Lazy: only fail when vector search is attempted if mismatch.
        self._stored_embedding_dim = int(stored)

    def _connect(self) -> sqlite3.Connection:
        connection = getattr(self._local, "connection", None)
        if connection is not None:
            try:
                connection.execute("SELECT 1")
                return connection
            except sqlite3.Error:
                try:
                    connection.close()
                except sqlite3.Error:
                    pass
                connection = None
        connection = sqlite3.connect(
            f"file:{self.sqlite_path}?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        # query_only may already be set by URI; apply remaining pragmas carefully
        for key, value in self._pragmas.items():
            if key == "query_only":
                continue
            if key == "journal_mode":
                # read-only URI ignores journal_mode writes
                continue
            try:
                if isinstance(value, str):
                    connection.execute(f"PRAGMA {key} = {value}")
                else:
                    connection.execute(f"PRAGMA {key} = {int(value)}")
            except sqlite3.Error:
                pass
        if self.vec_available:
            try_load_sqlite_vec(connection)
        self._local.connection = connection
        return connection

    def _ensure_aliases(self) -> None:
        if self._alias_entries is not None:
            return
        with self._alias_lock:
            if self._alias_entries is not None:
                return
            connection = self._connect()
            rows = connection.execute(
                f"""
                SELECT sku_code, canonical_code, also_published_as
                FROM sku_fact
                WHERE {_SKU_GRAIN}
                """
            ).fetchall()
            entries: list[tuple[str, str, str]] = []
            norm: dict[str, list[tuple[str, str]]] = {}
            for row in rows:
                sku = row["sku_code"]
                pairs = [(sku, "sku"), (row["canonical_code"] or sku, "canonical")]
                for alias in _loads(row["also_published_as"], []) or []:
                    pairs.append((str(alias), "alias"))
                for code, role in pairs:
                    if not code:
                        continue
                    entries.append((code, sku, role))
                    norm.setdefault(_normalize_code(code), []).append((sku, role))
            self._alias_entries = entries
            self._alias_norm = norm

    def _resolved_sku(self, code: str) -> str | None:
        self._ensure_aliases()
        assert self._alias_norm is not None
        hits = self._alias_norm.get(_normalize_code(code)) or []
        if hits:
            role_rank = {"sku": 0, "canonical": 1, "alias": 2}
            hits = sorted(hits, key=lambda item: role_rank.get(item[1], 9))
            return hits[0][0]
        fuzzy = self._fuzzy_alias_hits(code, limit=1)
        return fuzzy[0][0] if fuzzy else None

    def _fuzzy_alias_hits(
        self, query: str, *, limit: int
    ) -> list[tuple[str, str, float]]:
        """Return (sku_code, role, score 0-1) using case/hyphen-insensitive WRatio."""
        self._ensure_aliases()
        assert self._alias_entries is not None
        choices = {code: (sku, role) for code, sku, role in self._alias_entries}
        matches = process.extract(
            query,
            list(choices.keys()),
            scorer=fuzz.WRatio,
            processor=_normalize_code,
            limit=limit * 3,
            score_cutoff=70,
        )
        seen: set[str] = set()
        out: list[tuple[str, str, float]] = []
        for code, score, _ in matches:
            sku, role = choices[code]
            if sku in seen:
                continue
            seen.add(sku)
            out.append((sku, role, score / 100.0))
            if len(out) >= limit:
                break
        return out

    def resolve_product(self, **kw: Any) -> dict:
        query = str(kw["query"]).strip()
        family_hint = kw.get("family_hint")
        limit = max(1, min(int(kw.get("limit", 8)), 20))
        self._ensure_aliases()
        assert self._alias_entries is not None
        assert self._alias_norm is not None

        def family_ok(sku_code: str) -> bool:
            if not family_hint:
                return True
            connection = self._connect()
            row = connection.execute(
                f"SELECT family FROM sku_fact WHERE sku_code = ? AND {_SKU_GRAIN}",
                (sku_code,),
            ).fetchone()
            return bool(row and family_hint.lower() in (row["family"] or "").lower())

        exact = self._alias_norm.get(_normalize_code(query)) or []
        hits: list[dict[str, Any]] = []
        resolution = "exact"
        if exact:
            role_rank = {"sku": 0, "canonical": 1, "alias": 2}
            ordered = sorted(exact, key=lambda item: role_rank.get(item[1], 9))
            seen: set[str] = set()
            for sku, role in ordered:
                if sku in seen or not family_ok(sku):
                    continue
                seen.add(sku)
                hits.append(self._resolve_hit(sku, role, 1.0))
                if len(hits) >= limit:
                    break
        if not hits:
            resolution = "fuzzy"
            for sku, role, score in self._fuzzy_alias_hits(query, limit=limit):
                if not family_ok(sku):
                    continue
                hits.append(self._resolve_hit(sku, role, score))
        if not hits:
            resolution = "descriptive"
            connection = self._connect()
            like = f"%{query}%"
            params: list[Any] = [like, like]
            family_clause = ""
            if family_hint:
                family_clause = "AND family LIKE ?"
                params.append(f"%{family_hint}%")
            rows = connection.execute(
                f"""
                SELECT sku_code, canonical_code, family, path_text, description,
                       alias_reason
                FROM sku_fact
                WHERE {_SKU_GRAIN}
                  AND (description LIKE ? OR family LIKE ?)
                  {family_clause}
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()
            if not rows:
                fts_q = _fts_query(query)
                if fts_q:
                    fts = connection.execute(
                        """
                        SELECT DISTINCT c.sku_code
                        FROM chunk_fts
                        JOIN chunk c ON c.chunk_id = chunk_fts.rowid
                        WHERE chunk_fts MATCH ?
                        LIMIT ?
                        """,
                        (fts_q, limit),
                    ).fetchall()
                    for row in fts:
                        if family_ok(row["sku_code"]):
                            hits.append(
                                self._resolve_hit(row["sku_code"], "description", 0.2)
                            )
            else:
                for row in rows:
                    hits.append(
                        {
                            "sku_code": row["sku_code"],
                            "canonical_code": row["canonical_code"],
                            "family": row["family"],
                            "path_text": row["path_text"],
                            "match_role": "description",
                            "score": 0.25,
                            "description": row["description"],
                            "alias_reason": row["alias_reason"],
                        }
                    )
        result: dict[str, Any] = {"resolution": resolution, "hits": hits[:limit]}
        alias_hits = [hit for hit in hits if hit.get("match_role") == "alias"]
        if alias_hits:
            result["alias_note"] = alias_hits[0].get("alias_reason") or (
                "The supplied code is an alternate published spelling."
            )
        return result

    def _resolve_hit(self, sku_code: str, role: str, score: float) -> dict[str, Any]:
        connection = self._connect()
        row = connection.execute(
            f"""
            SELECT sku_code, canonical_code, family, path_text, description, alias_reason
            FROM sku_fact WHERE sku_code = ? AND {_SKU_GRAIN}
            """,
            (sku_code,),
        ).fetchone()
        if not row:
            return {
                "sku_code": sku_code,
                "canonical_code": sku_code,
                "family": None,
                "path_text": None,
                "match_role": role,
                "score": score,
                "description": None,
                "alias_reason": None,
            }
        return {
            "sku_code": row["sku_code"],
            "canonical_code": row["canonical_code"],
            "family": row["family"],
            "path_text": row["path_text"],
            "match_role": role,
            "score": score,
            "description": row["description"],
            "alias_reason": row["alias_reason"],
        }

    @lru_cache(maxsize=128)
    def _specs_for_family(self, family_key: str) -> tuple[dict[str, Any], ...]:
        connection = self._connect()
        if family_key == "*":
            rows = connection.execute(
                """
                SELECT family, spec_id,
                       min(spec_label) AS spec_label,
                       min(unit) AS unit,
                       min(value_kind) AS value_kind,
                       max(is_canonical_spec) AS is_canonical_spec,
                       count(DISTINCT sku_code) AS sku_count,
                       count(*) FILTER (WHERE value_kind = 'composite') AS composite_count,
                       min(COALESCE(value_min, value_num)) AS observed_min,
                       max(COALESCE(value_max, value_num)) AS observed_max
                FROM sku_fact
                WHERE is_sentinel = 0 AND spec_id IS NOT NULL
                GROUP BY family, spec_id
                ORDER BY family, spec_label, spec_id
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT family, spec_id,
                       min(spec_label) AS spec_label,
                       min(unit) AS unit,
                       min(value_kind) AS value_kind,
                       max(is_canonical_spec) AS is_canonical_spec,
                       count(DISTINCT sku_code) AS sku_count,
                       count(*) FILTER (WHERE value_kind = 'composite') AS composite_count,
                       min(COALESCE(value_min, value_num)) AS observed_min,
                       max(COALESCE(value_max, value_num)) AS observed_max
                FROM sku_fact
                WHERE is_sentinel = 0 AND spec_id IS NOT NULL
                  AND family LIKE ?
                GROUP BY family, spec_id
                ORDER BY family, spec_label, spec_id
                """,
                (f"%{family_key}%",),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def list_canonical_specs(self, **kw: Any) -> list[dict]:
        family = kw.get("family")
        contains = kw.get("spec_id_contains")
        canonical_only = bool(kw.get("canonical_only"))
        rows = list(self._specs_for_family(family or "*"))
        if contains:
            needle = contains.lower()
            rows = [
                row
                for row in rows
                if needle in (row.get("spec_id") or "").lower()
                or needle in (row.get("spec_label") or "").lower()
            ]
        if canonical_only:
            rows = [row for row in rows if row.get("is_canonical_spec")]
        return rows

    def taxonomy_browse(self, **kw: Any) -> dict:
        path = list(kw.get("path") or [])
        depth = len(path)
        if depth >= len(LEVEL_COLUMNS):
            return {
                "path": path,
                "children": [],
                "uncategorised": {
                    "children": [],
                    "note": (
                        "These are pricelist section names, not published C&S categories."
                    ),
                },
            }
        child_col = LEVEL_COLUMNS[depth]
        clauses = [f"{LEVEL_COLUMNS[i]} = ?" for i in range(depth)]
        params: list[Any] = list(path)
        clauses.append(f"{child_col} <> ?")
        params.append(NA)
        if segment := kw.get("market_segment"):
            clauses.append("market_segments_text LIKE ?")
            params.append(f"%{segment}%")
        where = " AND ".join(clauses)
        connection = self._connect()
        rows = connection.execute(
            f"""
            SELECT {child_col} AS name,
                   count(DISTINCT sku_code) AS sku_count,
                   CASE WHEN sum(CASE WHEN path_depth = ? THEN 1 ELSE 0 END) = count(*)
                        THEN 1 ELSE 0 END AS is_leaf
            FROM sku_fact
            WHERE {where}
            GROUP BY {child_col}
            ORDER BY name
            """,
            [depth + 1, *params],
        ).fetchall()
        children = []
        uncategorised = []
        for row in rows:
            item = {
                "name": row["name"],
                "sku_count": row["sku_count"],
                "is_leaf": bool(row["is_leaf"]),
                "description": None,
                "url": None,
            }
            if row["name"] == "_no_category" or (
                depth == 0 and row["name"] == "_no_category"
            ):
                uncategorised.append(item)
            elif path[:1] == ["_no_category"] or row["name"] == "_no_category":
                uncategorised.append(item)
            else:
                children.append(item)
        # Move any child literally named _no_category
        normal = [c for c in children if c["name"] != "_no_category"]
        uncategorised.extend(c for c in children if c["name"] == "_no_category")
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
            family = path[-1]
            facets = connection.execute(
                f"""
                SELECT sku_code, decoded FROM sku_fact
                WHERE family = ? AND {_SKU_GRAIN}
                LIMIT 200
                """,
                (family,),
            ).fetchall()
            axis_counts: dict[tuple[str, str, str], int] = {}
            for row in facets:
                decoded = _loads(row["decoded"], {}) or {}
                if not isinstance(decoded, dict):
                    continue
                for axis, spec in decoded.items():
                    if not isinstance(spec, dict):
                        continue
                    code = str(spec.get("code") or "")
                    meaning = str(spec.get("meaning") or "")
                    key = (axis, code, meaning)
                    axis_counts[key] = axis_counts.get(key, 0) + 1
            result["facets"] = [
                {"axis": a, "code": c, "meaning": m, "sku_count": n}
                for (a, c, m), n in sorted(axis_counts.items())
            ]
        return result

    def product_search(self, **kw: Any) -> dict:
        filters = kw.get("filters") or []
        limit = max(1, min(int(kw.get("limit", 20)), 100))
        connection = self._connect()

        base_clauses: list[str] = []
        base_params: list[Any] = []
        path = kw.get("path") or []
        for index, part in enumerate(path):
            if index >= len(LEVEL_COLUMNS):
                break
            base_clauses.append(f"{LEVEL_COLUMNS[index]} = ?")
            base_params.append(part)
        if family := kw.get("family"):
            base_clauses.append("family LIKE ?")
            base_params.append(f"%{family}%")
        if text := kw.get("text"):
            base_clauses.append(
                "(sku_code LIKE ? OR canonical_code LIKE ? OR family LIKE ? "
                "OR description LIKE ?)"
            )
            base_params.extend([f"%{text}%"] * 4)
        if segment := kw.get("market_segment"):
            base_clauses.append("market_segments_text LIKE ?")
            base_params.append(f"%{segment}%")
        if statuses := kw.get("price_status"):
            if isinstance(statuses, str):
                statuses = [statuses]
            placeholders = ",".join("?" for _ in statuses)
            base_clauses.append(f"price_status IN ({placeholders})")
            base_params.extend(statuses)

        applied: list[str] = []
        numeric_spec_ids: list[str] = []
        filter_groups: list[tuple[str, list[Any]]] = []
        for item in filters:
            spec_id, operator, value = item["spec_id"], item["op"], item["value"]
            if operator == "gte":
                pred = "spec_id = ? AND COALESCE(value_max, value_num) >= ?"
                params = [spec_id, value]
                numeric_spec_ids.append(spec_id)
            elif operator == "lte":
                pred = "spec_id = ? AND COALESCE(value_min, value_num) <= ?"
                params = [spec_id, value]
                numeric_spec_ids.append(spec_id)
            elif operator == "eq":
                pred = (
                    "spec_id = ? AND ? BETWEEN COALESCE(value_min, value_num) "
                    "AND COALESCE(value_max, value_num)"
                )
                params = [spec_id, value]
                numeric_spec_ids.append(spec_id)
            elif operator == "contains":
                pred = "spec_id = ? AND value_display LIKE ?"
                params = [spec_id, f"%{value}%"]
            else:
                return {"error": f"Unsupported filter operator: {operator}"}
            filter_groups.append((pred, params))
            applied.append(f"{spec_id} {operator} {item['value']}")

        if filter_groups:
            union_parts = []
            filter_params: list[Any] = []
            for pred, params in filter_groups:
                union_parts.append(
                    f"SELECT sku_code, spec_id FROM sku_fact WHERE {pred}"
                )
                filter_params.extend(params)
            matched_sql = f"""
                SELECT sku_code FROM (
                  {' UNION ALL '.join(union_parts)}
                )
                GROUP BY sku_code
                HAVING count(DISTINCT spec_id) = ?
            """
            filter_params.append(len(filter_groups))
            matched = {
                row["sku_code"]
                for row in connection.execute(matched_sql, filter_params).fetchall()
            }
        else:
            matched = None

        where = " AND ".join(base_clauses) if base_clauses else "1=1"
        rows = connection.execute(
            f"""
            SELECT * FROM sku_fact
            WHERE {_SKU_GRAIN} AND {where}
            ORDER BY sku_code
            """,
            base_params,
        ).fetchall()

        hits: list[dict[str, Any]] = []
        for row in rows:
            sku = row["sku_code"]
            if matched is not None and sku not in matched:
                continue
            if chunk_types := kw.get("has_chunk_type"):
                present = set(_loads(row["chunk_types"], []) or [])
                if not set(chunk_types).issubset(present):
                    continue
            if facets := kw.get("facets"):
                decoded = _loads(row["decoded"], {}) or {}
                ok = True
                for axis, code in facets.items():
                    spec = decoded.get(axis) if isinstance(decoded, dict) else None
                    if not isinstance(spec, dict):
                        ok = False
                        break
                    blob = f"{spec.get('code','')} {spec.get('meaning','')}".lower()
                    if str(code).lower() not in blob:
                        ok = False
                        break
                if not ok:
                    continue
            levels = [row[col] for col in LEVEL_COLUMNS if row[col] != NA]
            hits.append(
                {
                    "product_id": row["product_id"],
                    "sku_code": sku,
                    "canonical_code": row["canonical_code"],
                    "family": row["family"],
                    "path": levels,
                    "description": row["description"],
                    "url": row["url"],
                    "price_status": row["price_status"],
                    "price_inr": row["price_inr"],
                    "price_quotable": bool(row["price_quotable"]),
                    "decoded": _loads(row["decoded"], {}),
                }
            )

        hits.sort(
            key=lambda hit: (
                0 if hit.get("price_quotable") and hit.get("price_inr") is not None else 1,
                hit["price_inr"] if hit.get("price_inr") is not None else float("inf"),
                hit["sku_code"] or "",
            )
        )
        total = len(hits)
        limited = hits[:limit]
        return_specs = kw.get("return_specs") or []
        if limited and return_specs:
            codes = [h["sku_code"] for h in limited]
            placeholders = ",".join("?" for _ in codes)
            spec_ph = ",".join("?" for _ in return_specs)
            facts = connection.execute(
                f"""
                SELECT sku_code, product_id, spec_id, spec_label, unit, value_num,
                       value_min, value_max, value_display, value_kind,
                       source_of_truth, fact_source_pdf AS source_pdf,
                       fact_source_page AS source_page
                FROM sku_fact
                WHERE sku_code IN ({placeholders}) AND spec_id IN ({spec_ph})
                  AND is_sentinel = 0
                ORDER BY sku_code, spec_id
                """,
                [*codes, *return_specs],
            ).fetchall()
            by_sku: dict[str, list[dict]] = {}
            for fact in facts:
                by_sku.setdefault(fact["sku_code"], []).append(dict(fact))
            for hit in limited:
                hit["specs"] = by_sku.get(hit["sku_code"], [])

        composite_excluded = 0
        if numeric_spec_ids:
            base_where = " AND ".join(base_clauses) if base_clauses else "1=1"
            ph = ",".join("?" for _ in numeric_spec_ids)
            row = connection.execute(
                f"""
                SELECT count(DISTINCT sku_code) AS n
                FROM sku_fact
                WHERE {base_where} AND spec_id IN ({ph}) AND value_kind = 'composite'
                """,
                [*base_params, *numeric_spec_ids],
            ).fetchone()
            composite_excluded = int(row["n"] if row else 0)

        return {
            "hits": limited,
            "total_matched": total,
            "composite_excluded": composite_excluded,
            "filters_applied": applied,
            "widening_hint": (
                None
                if total
                else (
                    f"Relax {applied[-1]}"
                    if applied
                    else "Broaden the path, family, or text filter."
                )
            ),
        }

    def get_sku(self, sku_code: str, include: list[str], **kw: Any) -> dict:
        resolved = self._resolved_sku(sku_code)
        if not resolved:
            return {"error": f"No ordering code resolves from {sku_code!r}"}
        connection = self._connect()
        row = connection.execute(
            f"SELECT * FROM sku_fact WHERE sku_code = ? AND {_SKU_GRAIN}",
            (resolved,),
        ).fetchone()
        if not row:
            return {"error": f"No ordering code resolves from {sku_code!r}"}
        levels = [row[col] for col in LEVEL_COLUMNS if row[col] != NA]
        result: dict[str, Any] = {
            "product_id": row["product_id"],
            "sku_code": row["sku_code"],
            "canonical_code": row["canonical_code"],
            "family": row["family"],
            "description": row["description"],
            "url": row["url"],
            "price_status": row["price_status"],
            "peer_group": row["peer_group"],
            "path": levels,
            "headings": _loads(row["headings"], []),
            "attributes": _loads(row["attributes"], {}),
            "comparable_on": _loads(row["comparable_on"], []),
            "related_codes": _loads(row["related_codes"], []),
            "also_published_as": _loads(row["also_published_as"], []),
            "alias_reason": row["alias_reason"],
            "extraction": {
                "missing": _loads(row["extraction_missing"], []),
                "confidence": row["extraction_confidence"],
            },
            "fact_count": row["fact_count"],
        }
        if "decoded" in include:
            result["decoded"] = _loads(row["decoded"], {})
        if "facts" in include:
            facts = connection.execute(
                """
                SELECT spec_id, spec_label, unit, is_canonical_spec, value_num,
                       value_min, value_max, value_display, value_kind,
                       source_of_truth, fact_source_pdf AS source_pdf,
                       fact_source_page AS source_page,
                       fact_source_heading AS source_heading, fact_sentence
                FROM sku_fact
                WHERE sku_code = ? AND is_sentinel = 0 AND spec_id IS NOT NULL
                ORDER BY spec_id
                """,
                (resolved,),
            ).fetchall()
            result["facts"] = [dict(f) for f in facts]
        if "sources" in include:
            sources = []
            if row["brochure_md"]:
                sources.append(
                    {"ref_type": "brochure_md", "ref_name": row["brochure_md"], "page": None}
                )
            if row["product_page_url"]:
                sources.append(
                    {
                        "ref_type": "product_page",
                        "ref_name": row["product_page_url"],
                        "page": None,
                    }
                )
            for ref in _loads(row["pricelist_refs"], []) or []:
                sources.append(
                    {
                        "ref_type": "pricelist_pdf",
                        "ref_name": ref.get("pdf"),
                        "page": ref.get("page"),
                    }
                )
            result["sources"] = sources
        if "chunks" in include:
            chunk_types = kw.get("chunk_types")
            if chunk_types:
                ph = ",".join("?" for _ in chunk_types)
                chunks = connection.execute(
                    f"""
                    SELECT min(chunk_id) AS chunk_id, content AS text,
                           min(chunk_type) AS chunk_type, min(headings) AS headings,
                           count(*) AS duplicate_count
                    FROM chunk
                    WHERE sku_code = ? AND chunk_type IN ({ph})
                    GROUP BY content_hash, content
                    ORDER BY min(chunk_id)
                    """,
                    [resolved, *chunk_types],
                ).fetchall()
            else:
                chunks = connection.execute(
                    """
                    SELECT min(chunk_id) AS chunk_id, content AS text,
                           min(chunk_type) AS chunk_type, min(headings) AS headings,
                           count(*) AS duplicate_count
                    FROM chunk
                    WHERE sku_code = ?
                    GROUP BY content_hash, content
                    ORDER BY min(chunk_id)
                    """,
                    (resolved,),
                ).fetchall()
            result["chunks"] = [
                {
                    **dict(c),
                    "chunk_id": str(c["chunk_id"]),
                    "headings": _loads(c["headings"], []),
                }
                for c in chunks
            ]
        if "price" in include:
            result["price"] = self.get_price_detail([resolved])["prices"][0]
        if "peers" in include:
            result["peers"] = self.get_peer_group(resolved)
        return result

    def get_price_detail(self, sku_codes: list[str]) -> dict:
        prices: list[dict[str, Any]] = []
        connection = self._connect()
        for requested in sku_codes:
            resolved = self._resolved_sku(requested)
            if not resolved:
                prices.append({"sku_code": requested, "error": "unresolved"})
                continue
            row = connection.execute(
                f"""
                SELECT sku_code, price_status, price_quotable, price_observations
                FROM sku_fact WHERE sku_code = ? AND {_SKU_GRAIN}
                """,
                (resolved,),
            ).fetchone()
            observations = _loads(row["price_observations"], []) or []
            prices.append(
                {
                    "sku_code": resolved,
                    "price_status": row["price_status"],
                    "observations": observations,
                    "quotable": bool(row["price_quotable"]),
                }
            )
        return {"prices": prices}

    def get_peer_group(self, sku_code: str) -> dict:
        resolved = self._resolved_sku(sku_code)
        if not resolved:
            return {"error": f"No ordering code resolves from {sku_code!r}"}
        connection = self._connect()
        anchor = connection.execute(
            f"""
            SELECT peer_group, comparable_on, related_codes
            FROM sku_fact WHERE sku_code = ? AND {_SKU_GRAIN}
            """,
            (resolved,),
        ).fetchone()
        comparable = _loads(anchor["comparable_on"], []) or []
        related = _loads(anchor["related_codes"], []) or []
        if not anchor["peer_group"]:
            return {
                "sku_code": resolved,
                "peer_group": None,
                "comparable_on": comparable,
                "related_codes": related,
                "peers": [],
            }
        peers = connection.execute(
            f"""
            SELECT sku_code, family, decoded, price_status
            FROM sku_fact
            WHERE peer_group = ? AND {_SKU_GRAIN}
            ORDER BY sku_code
            """,
            (anchor["peer_group"],),
        ).fetchall()
        return {
            "sku_code": resolved,
            "peer_group": anchor["peer_group"],
            "comparable_on": comparable,
            "related_codes": related,
            "peers": [
                {
                    "sku_code": p["sku_code"],
                    "family": p["family"],
                    "decoded": _loads(p["decoded"], {}),
                    "price_status": p["price_status"],
                }
                for p in peers
            ],
        }

    def compare_skus(
        self, sku_codes: list[str], spec_ids: list[str] | None = None
    ) -> dict:
        connection = self._connect()
        resolved = [self._resolved_sku(code) for code in sku_codes]
        unresolved = [
            code for code, match in zip(sku_codes, resolved, strict=True) if not match
        ]
        codes = list(dict.fromkeys(code for code in resolved if code))
        if not codes:
            return {
                "error": "No supplied ordering code resolved",
                "unresolved_sku_codes": unresolved,
            }
        ph = ",".join("?" for _ in codes)
        metadata = connection.execute(
            f"""
            SELECT sku_code, peer_group, comparable_on
            FROM sku_fact WHERE sku_code IN ({ph}) AND {_SKU_GRAIN}
            """,
            codes,
        ).fetchall()
        groups = {row["peer_group"] for row in metadata if row["peer_group"]}
        peer_match = len(groups) == 1 and len(metadata) == len(codes)
        axes_source = "union"
        axes = list(spec_ids) if spec_ids else None
        if not axes and peer_match:
            sets = [set(_loads(row["comparable_on"], []) or []) for row in metadata]
            axes = sorted(set.intersection(*sets)) if sets else []
            axes_source = "comparable_on"
        if not axes:
            axes = [
                row["spec_id"]
                for row in connection.execute(
                    f"""
                    SELECT DISTINCT spec_id FROM sku_fact
                    WHERE sku_code IN ({ph}) AND is_sentinel = 0 AND spec_id IS NOT NULL
                    ORDER BY spec_id
                    """,
                    codes,
                ).fetchall()
            ]
        if not axes:
            return {
                "sku_codes": codes,
                "axes": [],
                "rows": {},
                "peer_group_match": peer_match,
                "axes_source": axes_source,
                "unresolved_sku_codes": unresolved,
            }
        axis_ph = ",".join("?" for _ in axes)
        facts = connection.execute(
            f"""
            SELECT sku_code, spec_id, value_display
            FROM sku_fact
            WHERE sku_code IN ({ph}) AND spec_id IN ({axis_ph}) AND is_sentinel = 0
            """,
            [*codes, *axes],
        ).fetchall()
        rows = {axis: {code: None for code in codes} for axis in axes}
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

    def search_documents(self, **kw: Any) -> list[dict]:
        if not kw.get("path") and not kw.get("family") and not kw.get("sku_code"):
            return [
                {
                    "error": (
                        "search_documents requires at least one family, path, "
                        "or sku_code filter"
                    ),
                    "mode": "none",
                }
            ]
        return self._search_documents_sqlite(kw)

    def _search_documents_sqlite(self, kw: dict[str, Any]) -> list[dict]:
        limit = max(1, min(int(kw.get("k", 6)), 20))
        family = kw.get("family")
        sku_code = kw.get("sku_code")
        path = list(kw.get("path") or [])
        chunk_types = kw.get("chunk_types")
        clauses: list[str] = ["1=1"]
        params: list[Any] = []
        for index, part in enumerate(path):
            if index >= len(LEVEL_COLUMNS):
                break
            clauses.append(f"{LEVEL_COLUMNS[index]} = ?")
            params.append(part)
        if family:
            clauses.append("family LIKE ?")
            params.append(f"%{family}%")
        if sku_code:
            clauses.append("sku_code = ?")
            params.append(sku_code)
        if chunk_types:
            ph = ",".join("?" for _ in chunk_types)
            clauses.append(f"chunk_type IN ({ph})")
            params.extend(chunk_types)
        where = " AND ".join(clauses)
        connection = self._connect()

        embeddings_loaded = bool(self._meta("embeddings_loaded"))
        if embeddings_loaded and self.vec_available:
            stored_dim = getattr(self, "_stored_embedding_dim", None)
            vector = embed(kw["query"], expected_dimension=stored_dim)
            if stored_dim and len(vector) != stored_dim:
                raise RuntimeError(
                    f"Query embedding dim {len(vector)} != catalogue {stored_dim}"
                )
            blob = _serialize_vec(vector)
            hash_counts = {
                row["content_hash"]: row["n"]
                for row in connection.execute(
                    f"""
                    SELECT content_hash, count(*) AS n FROM chunk
                    WHERE {where} GROUP BY content_hash
                    """,
                    params,
                ).fetchall()
            }
            rows = connection.execute(
                f"""
                SELECT chunk_id, sku_code, family, chunk_type, content AS text,
                       headings, brochure_md, content_hash,
                       vec_distance_cosine(embedding, ?) AS distance
                FROM chunk
                WHERE {where} AND embedding IS NOT NULL
                ORDER BY distance
                LIMIT ?
                """,
                [blob, *params, limit * 5],
            ).fetchall()
            deduped: list[dict[str, Any]] = []
            seen_hash: set[str] = set()
            for row in rows:
                if row["content_hash"] in seen_hash:
                    continue
                seen_hash.add(row["content_hash"])
                distance = float(row["distance"])
                deduped.append(
                    {
                        "chunk_id": str(row["chunk_id"]),
                        "text": row["text"],
                        "chunk_type": row["chunk_type"],
                        "headings": _loads(row["headings"], []),
                        "sku_code": row["sku_code"],
                        "family": row["family"],
                        "distance": distance,
                        "score": 1.0 - distance,
                        "shared_by_sku_count": hash_counts.get(row["content_hash"], 1),
                        "brochure_md": row["brochure_md"],
                        "mode": "vector",
                    }
                )
                if len(deduped) >= limit:
                    break
            if deduped:
                return deduped

        safe_query = _fts_query(kw["query"])
        if not safe_query:
            return []
        # Fetch a wider FTS pool, then apply structured filters in Python so we
        # do not have to rewrite the JOIN predicate for every level column.
        fts_rows = connection.execute(
            """
            SELECT c.chunk_id, c.sku_code, c.family, c.chunk_type, c.content AS text,
                   c.headings, c.brochure_md, c.content_hash,
                   c.division, c.product_group, c.product_subgroup, c.product_range,
                   bm25(chunk_fts) AS rank
            FROM chunk_fts
            JOIN chunk c ON c.chunk_id = chunk_fts.rowid
            WHERE chunk_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (safe_query, max(limit * 50, 100)),
        ).fetchall()
        deduped = []
        seen_hash: set[str] = set()
        for row in fts_rows:
            if family and family.lower() not in (row["family"] or "").lower():
                continue
            if sku_code and row["sku_code"] != sku_code:
                continue
            if chunk_types and row["chunk_type"] not in chunk_types:
                continue
            ok = True
            for index, part in enumerate(path):
                if row[LEVEL_COLUMNS[index]] != part:
                    ok = False
                    break
            if not ok:
                continue
            if row["content_hash"] in seen_hash:
                continue
            seen_hash.add(row["content_hash"])
            deduped.append(
                {
                    "chunk_id": str(row["chunk_id"]),
                    "text": row["text"],
                    "chunk_type": row["chunk_type"],
                    "headings": _loads(row["headings"], []),
                    "sku_code": row["sku_code"],
                    "family": row["family"],
                    "score": float(row["rank"]) if row["rank"] is not None else 0.0,
                    "shared_by_sku_count": 1,
                    "brochure_md": row["brochure_md"],
                    "mode": "lexical",
                }
            )
            if len(deduped) >= limit:
                break
        return deduped

    def execute_sql(self, sql: str) -> dict:
        try:
            connection = self._connect()
            # analytics may need write-disabled connection; SELECT only
            cursor = connection.execute(sql)
            columns = [col[0] for col in cursor.description or []]
            rows = cursor.fetchall()
            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "row_count": len(rows),
            }
        except sqlite3.Error as exc:
            return {"columns": [], "rows": [], "row_count": 0, "error": str(exc)}
