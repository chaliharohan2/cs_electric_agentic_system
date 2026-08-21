"""SQLite catalogue adapter over the built ``sku_fact`` / ``chunk`` artifact."""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import struct
import threading
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz, process

from cs_agent.backends.grouped_search import (
    GROUP_BY_SCOPE_ERROR,
    grouped_product_search,
    group_key,
    has_search_scope,
)
from cs_agent.backends.matching import family_terms, matches, matches_any, squash
from cs_agent.backends.path_levels import LEVEL_COLUMNS, NA
from cs_agent.backends.payload_shape import (
    PEER_SCOPE_FIELDS,
    SEARCH_SCOPE_FIELDS,
    flatten_decoded,
    hoist_scope,
)
from cs_agent.backends.spec_envelope import (
    NESTED_REDUNDANT,
    compact_fact,
    group_specs,
)
from cs_agent.backends.vec_support import try_load_sqlite_vec
from cs_agent.config.limits import get_limits
from cs_agent.embeddings import embed

logger = logging.getLogger(__name__)

_SKU_GRAIN = (
    "row_id IN (SELECT min(row_id) FROM sku_fact GROUP BY sku_code)"
)


def _path_prefix_clauses(path: list[str] | None) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for index, part in enumerate(path or []):
        if index >= len(LEVEL_COLUMNS):
            break
        clauses.append(f"{LEVEL_COLUMNS[index]} = ?")
        params.append(part)
    return clauses, params


def _family_like_clause(family: Any) -> tuple[str | None, list[Any]]:
    terms = family_terms(family)
    if not terms:
        return None, []
    return "(" + " OR ".join("family LIKE ?" for _ in terms) + ")", [
        f"%{term}%" for term in terms
    ]


def _not_shared_note(dropped: dict[str, list[str]], group_by: str) -> dict[str, Any]:
    return {
        "note": (
            f"These specifications are not published by every {group_by} in "
            "scope, so they were left off the hits: an empty cell would read as "
            "a product difference rather than a gap in the catalogue. Each is "
            "listed against the groups that do publish it — search that group "
            "alone to see it."
        ),
        "spec_ids": dict(sorted(dropped.items())),
    }


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


def _clip(text: Any, limit: int) -> Any:
    """Trim brochure prose to a readable head, marking what was dropped.

    Chunks run to 11,700 characters, and a handful of them fills a local
    model's context window. The opening of a chunk carries the claim; the tail
    is usually a continuation table the agent can fetch deliberately with
    get_sku if it turns out to matter.
    """
    if not isinstance(text, str) or len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}… [truncated {len(text) - limit} characters]"


def _normalize_code(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _fts_query(value: str) -> str:
    """Turn free text into a safe FTS5 MATCH query (no column operators)."""
    tokens = re.findall(r"[A-Za-z0-9_]+", value)
    return " ".join(tokens)


# Below this, a suggestion is noise. Calibrated against the built catalogue:
# "winbrek" scores 77 on MCCB – Winbreak and "distribushion board" 89 on
# Distribution Boards, while "solar inverter" — which C&S does not make — tops
# out at 72 against "Meter". A list of unrelated branches reads as an answer.
_CLOSE_ENOUGH = 75


def _closest(
    wanted: str, branches: Sequence[dict[str, Any]], limit: int = 6
) -> list[str]:
    """Catalogue branches worth trying instead of one that matched nothing.

    Scored on the family name rather than the whole path, because that is what
    a customer types: against the full ``Low Voltage Products and Solutions >
    Circuit Breakers > Moulded Case Circuit Breakers > MCCB – Winbreak`` a
    seven-character typo is swamped by eighty characters it never mentioned,
    and the right family scored below an unrelated one. Both sides are squashed
    to alphanumerics first so an en dash or a curly quote cannot cost a match.

    An empty result that says nothing is what makes a specialist re-issue the
    same guess until its budget runs out.
    """
    names = {squash(b["family"]): b for b in branches if b["family"]}
    hits = process.extract(
        squash(wanted),
        list(names),
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=_CLOSE_ENOUGH,
    )
    return [
        " > ".join(names[key]["path"]) or names[key]["family"]
        for key, _score, _i in hits
    ]


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
                SELECT sku_code, family, path_text, description,
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
            SELECT sku_code, family, path_text, description, alias_reason
            FROM sku_fact WHERE sku_code = ? AND {_SKU_GRAIN}
            """,
            (sku_code,),
        ).fetchone()
        if not row:
            return {
                "sku_code": sku_code,
                "family": None,
                "path_text": None,
                "match_role": role,
                "score": score,
                "description": None,
                "alias_reason": None,
            }
        return {
            "sku_code": row["sku_code"],
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

    def _specs_for_scope(
        self, path: list[str] | None, family: Any
    ) -> list[dict[str, Any]]:
        level_select = "".join(f"{col}, " for col in LEVEL_COLUMNS)
        level_group = level_select
        clauses = ["is_sentinel = 0", "spec_id IS NOT NULL"]
        params: list[Any] = []
        path_clauses, path_params = _path_prefix_clauses(path)
        clauses.extend(path_clauses)
        params.extend(path_params)
        family_sql, family_params = _family_like_clause(family)
        if family_sql:
            clauses.append(family_sql)
            params.extend(family_params)
        rows = self._connect().execute(
            f"""
            SELECT family, {level_select} spec_id,
                   min(spec_label) AS spec_label,
                   min(unit) AS unit,
                   min(value_kind) AS value_kind,
                   max(is_canonical_spec) AS is_canonical_spec,
                   count(DISTINCT sku_code) AS sku_count,
                   count(*) FILTER (WHERE value_kind = 'composite') AS composite_count,
                   min(COALESCE(value_min, value_num)) AS observed_min,
                   max(COALESCE(value_max, value_num)) AS observed_max
            FROM sku_fact
            WHERE {' AND '.join(clauses)}
            GROUP BY family, {level_group} spec_id
            ORDER BY family, spec_label, spec_id
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def _unmatched_family_terms_sql(self, family: Any) -> list[str]:
        connection = self._connect()
        missed: list[str] = []
        for term in family_terms(family):
            row = connection.execute(
                "SELECT 1 FROM sku_fact WHERE family LIKE ? LIMIT 1",
                (f"%{term}%",),
            ).fetchone()
            if not row:
                missed.append(term)
        return missed

    def spec_rows(self, **kw: Any) -> list[dict[str, Any]]:
        """Flat per-(family, spec_id) registry rows for a scope.

        The unshaped form, for callers that do their own reduction: the
        analytics subgraph budgets them into a starting vocabulary, and the
        tool layer groups and intersects them. Neither wants the other's shape.
        """
        family = kw.get("family")
        path = kw.get("path") or None
        if isinstance(path, list) and not path:
            path = None
        if path:
            rows = self._specs_for_scope(path, family)
        else:
            terms = family_terms(family)
            if not terms:
                rows = list(self._specs_for_family("*"))
            else:
                seen: set[tuple[str, str]] = set()
                rows = []
                for term in terms:
                    for row in self._specs_for_family(term):
                        key = (row["family"], row["spec_id"])
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append(row)
        if contains := kw.get("spec_id_contains"):
            needle = contains.lower()
            rows = [
                row
                for row in rows
                if needle in (row.get("spec_id") or "").lower()
                or needle in (row.get("spec_label") or "").lower()
            ]
        if kw.get("canonical_only"):
            rows = [row for row in rows if row.get("is_canonical_spec")]
        return rows

    def _groups_in_scope(self, path: Any, family: Any, group_by: str) -> list[str]:
        """Every group the scope covers, including any that match no spec.

        Read from the catalogue rather than from the matched rows, because a
        family holding none of the requested specs still has to count against
        the intersection — otherwise a spec one family out of three publishes
        comes back marked as shared by all three.
        """
        column = "family" if group_by == "family" else group_by
        clauses = ["is_sentinel = 0"]
        params: list[Any] = []
        path_clauses, path_params = _path_prefix_clauses(path)
        clauses.extend(path_clauses)
        params.extend(path_params)
        family_sql, family_params = _family_like_clause(family)
        if family_sql:
            clauses.append(family_sql)
            params.extend(family_params)
        rows = self._connect().execute(
            f"SELECT DISTINCT {column} AS g FROM sku_fact "
            f"WHERE {' AND '.join(clauses)} AND {column} IS NOT NULL "
            f"AND {column} != ? ORDER BY 1",
            [*params, NA],
        ).fetchall()
        return [str(row["g"]) for row in rows]

    def list_canonical_specs(self, **kw: Any) -> dict:
        family = kw.get("family")
        path = kw.get("path") or None
        if isinstance(path, list) and not path:
            path = None
        group_by = kw.get("group_by") or "family"
        rows = [compact_fact(row) for row in self.spec_rows(**kw)]
        result = group_specs(
            rows,
            groups=self._groups_in_scope(path, family, group_by),
            group_by=group_by,
            path=path,
            family=family,
        )
        missed = self._unmatched_family_terms_sql(family)
        if missed:
            result["families_not_found"] = missed
        return result

    # ------------------------------------------------------------------ map

    @lru_cache(maxsize=1)
    def _catalogue_branches(self) -> tuple[dict[str, Any], ...]:
        """Every populated branch of the taxonomy, with its SKU count.

        Grouped on the level columns themselves — division, product_group,
        product_subgroup, product_range — rather than on the rendered
        ``path_text``, because those columns are what the rest of the toolchain
        takes as arguments: a `taxonomy_browse` path is a list of literal level
        values, and `product_search` filters on them. Grouping on the rendered
        string and splitting it back would put a parsed value where the real one
        was available. The two agree exactly on the built catalogue (66 groups
        either way, and the levels reconstruct every path_text), so this is a
        change of provenance rather than of result.

        `family` stays in the key because it is the only thing separating the
        eleven unplaced branches, which all share the same all-N/A level tuple.

        Cached for the process because it is small and fixed: 56 published paths
        plus a handful of unplaced families. Matching then runs over that in
        Python rather than in SQL, because catalogue labels need the punctuation
        folding in ``backends.matching`` — ``WiNtrip 'S' Modular MCB`` carries
        curly quotes and ``ACB - AH-AHA`` an en dash, and a LIKE would miss both.
        """
        levels = ", ".join(LEVEL_COLUMNS)
        rows = self._connect().execute(
            f"""
            SELECT {levels},
                   family,
                   max(market_segments_text) AS market_segments_text,
                   count(DISTINCT sku_code)  AS sku_count
            FROM sku_fact
            GROUP BY {levels}, family
            """
        ).fetchall()
        published = self._taxonomy_levels()
        branches = []
        for row in rows:
            # 'N/A' is the padding the build writes for a level this branch does
            # not reach, so it marks absence rather than naming a category.
            named = {
                column: row[column]
                for column in LEVEL_COLUMNS
                if row[column] and row[column] != NA
            }
            path = [named[column] for column in LEVEL_COLUMNS if column in named]
            path_text = " > ".join(path)
            page = published.get(path_text) or {}
            segments = [
                part
                for part in (row["market_segments_text"] or "").split("|")
                if part
            ]
            branches.append(
                {
                    **named,
                    "family": row["family"],
                    # The literal level values again as a list, because that is
                    # the argument taxonomy_browse and product_search take.
                    "path": path,
                    "sku_count": row["sku_count"],
                    "description": page.get("description"),
                    "url": page.get("url"),
                    "market_segments": segments,
                    # A branch the pricelist named but the published taxonomy
                    # never placed: `family` is set, every level is 'N/A'.
                    "_uncategorised": not path,
                    # Matched against, never returned: the path a customer would
                    # recognise, or the family for an unplaced branch.
                    "_haystack": path_text or row["family"] or "",
                }
            )
        return tuple(branches)

    def catalogue_map(self, **kw: Any) -> dict:
        path_text = (kw.get("path_text") or "").strip()
        market_segment = (kw.get("market_segment") or "").strip()
        include_uncategorised = kw.get("include_uncategorised", True)
        limit = max(1, min(int(kw.get("limit", 40)), 100))

        placed: list[dict[str, Any]] = []
        unplaced: list[dict[str, Any]] = []
        for branch in self._catalogue_branches():
            if branch["_uncategorised"] and not include_uncategorised:
                continue
            if path_text and not matches(branch["_haystack"], path_text):
                continue
            if market_segment and not matches_any(
                branch["market_segments"], market_segment
            ):
                continue
            bucket = unplaced if branch["_uncategorised"] else placed
            bucket.append({k: v for k, v in branch.items() if not k.startswith("_")})

        # Largest first: a family with 408 SKUs is what the customer meant more
        # often than one with 6, and `limit` cuts from the bottom.
        placed.sort(key=lambda b: (-b["sku_count"], b["family"]))
        unplaced.sort(key=lambda b: (-b["sku_count"], b["family"]))

        # `path_text` is not echoed back. It is the caller's own argument,
        # visible in the tool call immediately above the result, and reading it
        # back told the model nothing it had not just written. `market_segment`
        # stays because it is validated against a closed vocabulary, so seeing
        # which value actually took effect is an answer rather than an echo.
        matched_on = {"market_segment": market_segment} if market_segment else {}
        result: dict[str, Any] = {
            "groups": placed[:limit],
            "total_groups": len(placed),
            "total_skus": sum(branch["sku_count"] for branch in placed),
        }
        if matched_on:
            result["matched_on"] = matched_on
        if len(placed) > limit:
            result["truncated"] = (
                f"Showing {limit} of {len(placed)} matching branches, largest "
                "first. Narrow path_text or raise limit for the rest."
            )
        if unplaced:
            result["uncategorised"] = {
                "groups": unplaced[:limit],
                "total_skus": sum(branch["sku_count"] for branch in unplaced),
                "note": (
                    "These are pricelist section names, not published C&S "
                    "categories, so they have no path, description or URL. "
                    "product_search with family= still reaches their SKUs."
                ),
            }
        if not placed and not unplaced:
            result["no_match"] = self._map_miss(path_text, market_segment)
        return result

    def _map_miss(self, path_text: str, market_segment: str) -> dict[str, Any]:
        """Why a map call came back empty, and what to try instead.

        An empty result that says nothing is what makes a specialist re-issue
        the same guess until its budget runs out, so both filters report the
        vocabulary they actually accept.
        """
        miss: dict[str, Any] = {}
        if path_text:
            # Only when something actually scored: a list of unrelated branches
            # reads as an answer and sends the agent down a wrong path.
            if close := _closest(path_text, self._catalogue_branches()):
                miss["closest_paths"] = close
        if market_segment:
            miss["known_market_segments"] = sorted(
                {
                    segment
                    for branch in self._catalogue_branches()
                    for segment in branch["market_segments"]
                }
            )
        miss["note"] = (
            "No catalogue branch matched. "
            + (
                "Nothing scored close to that name, so C&S may not publish it "
                "under any path — try product_search, which also matches "
                "ordering codes and descriptions, before concluding it does "
                "not exist. "
                if path_text and "closest_paths" not in miss
                else ""
            )
            + "taxonomy_browse with path=[] lists the divisions."
        )
        return miss

    @lru_cache(maxsize=1)
    def _taxonomy_levels(self) -> dict[str, dict[str, Any]]:
        """Published page metadata per taxonomy node, keyed on its path text.

        Absent from artifacts built before the taxonomy_level table existed, so
        a missing table degrades to no descriptions rather than failing browse.
        """
        try:
            rows = self._connect().execute(
                """
                SELECT path_text, name, level, url, description, is_leaf, page_type
                FROM taxonomy_level
                """
            ).fetchall()
        except sqlite3.Error:
            logger.warning(
                "taxonomy_level table missing; rebuild the catalogue to get "
                "published category descriptions and URLs"
            )
            return {}
        return {row["path_text"]: dict(row) for row in rows}

    def _facets_under(
        self, where: str, params: list[Any]
    ) -> tuple[list[dict[str, Any]], int]:
        """Decoded ordering-code axes for every SKU under a path prefix.

        Counted over the whole branch rather than a sample: the count is what
        tells the agent an axis value exists, so an undercount reads as "C&S
        does not make that variant".

        Returns the highest-coverage rows and the total number found. The root
        of the catalogue yields 1,377 of them — around 28k tokens, useless to
        read and enough to crowd out the rest of the prompt — so the caller
        caps what it shows while still reporting how many exist.
        """
        rows = self._connect().execute(
            f"SELECT decoded FROM sku_fact WHERE {where} AND {_SKU_GRAIN}",
            params,
        ).fetchall()
        axis_counts: dict[tuple[str, str, str], int] = {}
        meanings: dict[tuple[str, str, str], Any] = {}
        for row in rows:
            decoded = _loads(row["decoded"], {}) or {}
            if not isinstance(decoded, dict):
                continue
            for axis, spec in decoded.items():
                if not isinstance(spec, dict):
                    continue
                meaning = spec.get("meaning")
                # An axis meaning may be a scalar or an object such as
                # {"ka": 50, "volts": 415}. Group on a stable rendering, but
                # return the value itself so the model reads JSON, not a repr.
                key = (
                    axis,
                    str(spec.get("code") or ""),
                    json.dumps(meaning, sort_keys=True, default=str),
                )
                axis_counts[key] = axis_counts.get(key, 0) + 1
                meanings[key] = meaning
        facets = [
            {"axis": key[0], "code": key[1], "meaning": meanings[key], "sku_count": count}
            for key, count in sorted(
                axis_counts.items(), key=lambda item: (item[0][0], -item[1], item[0][1])
            )
        ]
        total = len(facets)
        # Rank by coverage for the cut, then restore axis grouping so the kept
        # rows still read as axes rather than a shuffled list. The cut is by
        # position, not by key: one (axis, code) pair can carry several decoded
        # meanings, and matching on the pair would let a cap of 60 return 80.
        cap = get_limits().max_facet_rows
        if total > cap:
            keep = sorted(facets, key=lambda item: -item["sku_count"])[:cap]
            facets = sorted(
                keep, key=lambda item: (item["axis"], -item["sku_count"], item["code"])
            )
        return facets, total

    def taxonomy_browse(self, **kw: Any) -> dict:
        path = [str(part) for part in (kw.get("path") or [])][: len(LEVEL_COLUMNS)]
        depth = len(path)
        connection = self._connect()

        # Every SKU sitting under the requested path. Shared by the child listing
        # and the facet roll-up so both describe the same branch.
        branch_clauses = [f"{LEVEL_COLUMNS[index]} = ?" for index in range(depth)]
        branch_params: list[Any] = list(path)
        if segment := kw.get("market_segment"):
            branch_clauses.append("market_segments_text LIKE ?")
            branch_params.append(f"%{segment}%")
        branch_where = " AND ".join(branch_clauses) if branch_clauses else "1=1"

        children: list[dict[str, Any]] = []
        uncategorised: list[dict[str, Any]] = []
        at_deepest_level = depth >= len(LEVEL_COLUMNS)
        if not at_deepest_level:
            child_col = LEVEL_COLUMNS[depth]
            rows = connection.execute(
                f"""
                SELECT {child_col} AS name,
                       count(DISTINCT sku_code) AS sku_count,
                       CASE WHEN sum(CASE WHEN path_depth = ? THEN 1 ELSE 0 END)
                                 = count(*)
                            THEN 1 ELSE 0 END AS is_leaf
                FROM sku_fact
                WHERE {branch_where} AND {child_col} <> ?
                GROUP BY {child_col}
                ORDER BY name
                """,
                [depth + 1, *branch_params, NA],
            ).fetchall()
            published = self._taxonomy_levels()
            for row in rows:
                page = published.get(" > ".join([*path, row["name"]])) or {}
                item = {
                    "name": row["name"],
                    "sku_count": row["sku_count"],
                    "is_leaf": bool(row["is_leaf"]),
                    "description": page.get("description"),
                    "url": page.get("url"),
                }
                # A branch is uncategorised when it is the _no_category holding
                # folder or sits anywhere beneath it.
                if row["name"] == "_no_category" or path[:1] == ["_no_category"]:
                    uncategorised.append(item)
                else:
                    children.append(item)

        result: dict[str, Any] = {
            "path": path,
            "children": children,
            "uncategorised": {
                "children": uncategorised,
                "note": (
                    "These are pricelist section names, not published C&S categories."
                ),
            },
        }
        if path and (node := self._taxonomy_levels().get(" > ".join(path))):
            result["node"] = {
                "name": node["name"],
                "description": node["description"],
                "url": node["url"],
                "page_type": node["page_type"],
            }
        if at_deepest_level:
            result["note"] = (
                f"{' > '.join(path)} is the deepest catalogue level, so it has no "
                "child categories. Use product_search with this family for its SKUs."
            )
        if kw.get("include_facets"):
            facets, total = self._facets_under(branch_where, branch_params)
            result["facets"] = facets
            result["facet_axis_value_count"] = total
            if total > len(facets):
                result["facets_truncated"] = (
                    f"Showing the {len(facets)} most common of {total} ordering-code "
                    "axis values under this path. Browse into a child category for "
                    "the full set of that branch; absence from this list does not "
                    "mean the variant does not exist."
                )
        return result

    def _search_hit_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        """One hit, addressed by its ordering code.

        `product_id` is deliberately absent. It is a build-source row id that
        several distinct ordering codes can share, so it identifies nothing the
        caller can act on and invites exactly the grouping that collapsed
        `CE20113` into `CE20113NR`. The ordering code is the identity.

        `canonical_code` is absent for a duller reason: it repeated `sku_code`
        on 11,217 of the catalogue's 11,250 ordering codes, and a search answers
        with the code you order by. `resolve_product` is where a code that is
        published under two spellings gets sorted out, and it still says so
        through `match_role` and `alias_note`.

        `family`, `path` and `url` are set here and hoisted out again by
        `hoist_scope` at the end of the search when they turn out to hold the
        same value on every hit — which, scoped to one family, they always do.
        Setting them per row first is what lets the grouping code read them.
        """
        levels = [row[col] for col in LEVEL_COLUMNS if row[col] != NA]
        hit = {
            "sku_code": row["sku_code"],
            "family": row["family"],
            "path": levels,
            "description": row["description"],
            "url": row["url"],
            "price_status": row["price_status"],
            "price_inr": row["price_inr"],
            "price_quotable": bool(row["price_quotable"]),
        }
        # An ordering code nothing decoded gets no `decoded` key at all, rather
        # than an empty object announcing that it has nothing to say.
        if decoded := flatten_decoded(_loads(row["decoded"], {})):
            hit["decoded"] = decoded
        return hit

    def _row_passes_chunk_and_facets(
        self, row: sqlite3.Row, kw: dict[str, Any]
    ) -> bool:
        if chunk_types := kw.get("has_chunk_type"):
            present = set(_loads(row["chunk_types"], []) or [])
            if not set(chunk_types).issubset(present):
                return False
        if facets := kw.get("facets"):
            decoded = _loads(row["decoded"], {}) or {}
            for axis, code in facets.items():
                spec = decoded.get(axis) if isinstance(decoded, dict) else None
                if not isinstance(spec, dict):
                    return False
                blob = f"{spec.get('code','')} {spec.get('meaning','')}".lower()
                if str(code).lower() not in blob:
                    return False
        return True

    def _attach_return_specs(
        self,
        connection: sqlite3.Connection,
        hits: list[dict[str, Any]],
        return_specs: list[str],
    ) -> None:
        """Hang the requested specifications on each hit, keyed by spec_id.

        `spec_label` is selected. It was dropped here once, on the grounds that
        274 attached rows on a measured call carried only the seven labels the
        caller had already named by id. The measurement was right and the
        conclusion was wrong: a spec_id is not always a readable form of its
        label. Across the built catalogue 1,005 of 1,650 distinct
        (spec_id, spec_label) pairs — 61% — cannot be recovered from the id,
        and the failures are the ones that change meaning: `10_12` is published
        as "10, 12" and `10_16` as "10-16", so the id alone cannot say whether
        two values or a span is meant, and `1no_1nc_for_125_250_a` is
        "1NO + 1NC for 125~250 A". Restating a definition per row is the price
        of not guessing at it.
        """
        if not hits or not return_specs:
            return
        codes = [hit["sku_code"] for hit in hits]
        placeholders = ",".join("?" for _ in codes)
        spec_ph = ",".join("?" for _ in return_specs)
        facts = connection.execute(
            f"""
            SELECT sku_code, spec_id, spec_label, unit, value_num,
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
            by_sku.setdefault(fact["sku_code"], []).append(
                compact_fact(dict(fact), drop=NESTED_REDUNDANT)
            )
        for hit in hits:
            hit["specs"] = by_sku.get(hit["sku_code"], [])

    def _shared_return_specs(
        self, kw: dict[str, Any], return_specs: list[str]
    ) -> tuple[list[str], dict[str, list[str]]]:
        """Split requested specs into those the whole scope publishes and the rest.

        A comparison across families can only be drawn on a specification all of
        them carry. Attaching one that only some publish invites the reader to
        treat its absence elsewhere as a difference in the product, when it is a
        difference in what the catalogue records. The unshared ids are named in
        the result instead, so the caller can ask for one family alone.
        """
        group_by = kw.get("group_by") or "family"
        groups = self._groups_in_scope(kw.get("path"), kw.get("family"), group_by)
        if len(groups) <= 1 or not return_specs:
            return list(return_specs), {}
        column = "family" if group_by == "family" else group_by
        clauses = ["is_sentinel = 0"]
        params: list[Any] = []
        path_clauses, path_params = _path_prefix_clauses(kw.get("path"))
        clauses.extend(path_clauses)
        params.extend(path_params)
        family_sql, family_params = _family_like_clause(kw.get("family"))
        if family_sql:
            clauses.append(family_sql)
            params.extend(family_params)
        spec_ph = ",".join("?" for _ in return_specs)
        rows = self._connect().execute(
            f"SELECT DISTINCT spec_id, {column} AS g FROM sku_fact "
            f"WHERE {' AND '.join(clauses)} AND spec_id IN ({spec_ph})",
            [*params, *return_specs],
        ).fetchall()
        holders: dict[str, set[str]] = {}
        for row in rows:
            holders.setdefault(row["spec_id"], set()).add(str(row["g"]))
        wanted = set(groups)
        kept, dropped = [], {}
        for spec_id in return_specs:
            held = holders.get(spec_id, set()) & wanted
            if held == wanted:
                kept.append(spec_id)
            else:
                dropped[spec_id] = sorted(held)
        return kept, dropped

    def _spec_ids_by_group(
        self,
        connection: sqlite3.Connection,
        in_scope: list[dict[str, Any]],
        group_by: str,
        filter_spec_ids: list[str],
    ) -> dict[str, set[str]]:
        published: dict[str, set[str]] = {}
        if not in_scope or not filter_spec_ids:
            return published
        codes = [hit["sku_code"] for hit in in_scope]
        sku_group = {hit["sku_code"]: group_key(hit, group_by) for hit in in_scope}
        placeholders = ",".join("?" for _ in codes)
        spec_ph = ",".join("?" for _ in filter_spec_ids)
        rows = connection.execute(
            f"""
            SELECT sku_code, spec_id FROM sku_fact
            WHERE sku_code IN ({placeholders}) AND spec_id IN ({spec_ph})
              AND is_sentinel = 0
            """,
            [*codes, *filter_spec_ids],
        ).fetchall()
        for row in rows:
            key = sku_group.get(row["sku_code"])
            if key is None:
                continue
            published.setdefault(key, set()).add(row["spec_id"])
        return published

    def product_search(self, **kw: Any) -> dict:
        group_by = kw.get("group_by")
        if group_by and not has_search_scope(kw.get("path"), kw.get("family")):
            return {"error": GROUP_BY_SCOPE_ERROR}
        filters = kw.get("filters") or []
        limit = max(1, min(int(kw.get("limit", 20)), 100))
        connection = self._connect()

        base_clauses: list[str] = []
        base_params: list[Any] = []
        path_clauses, path_params = _path_prefix_clauses(kw.get("path") or [])
        base_clauses.extend(path_clauses)
        base_params.extend(path_params)
        family_sql, family_params = _family_like_clause(kw.get("family"))
        if family_sql:
            base_clauses.append(family_sql)
            base_params.extend(family_params)
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

        in_scope: list[dict[str, Any]] = []
        for row in rows:
            if not self._row_passes_chunk_and_facets(row, kw):
                continue
            in_scope.append(self._search_hit_from_row(row))

        in_scope.sort(
            key=lambda hit: (
                0 if hit.get("price_quotable") and hit.get("price_inr") is not None else 1,
                hit["price_inr"] if hit.get("price_inr") is not None else float("inf"),
                hit["sku_code"] or "",
            )
        )
        matched_codes = (
            {hit["sku_code"] for hit in in_scope}
            if matched is None
            else {hit["sku_code"] for hit in in_scope if hit["sku_code"] in matched}
        )

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

        missed = self._unmatched_family_terms_sql(kw.get("family"))
        return_specs = kw.get("return_specs") or []
        empty_hint = (
            f"Relax {applied[-1]}"
            if applied
            else "Broaden the path, family, or text filter."
        )

        if group_by:
            filter_spec_ids = [item["spec_id"] for item in filters]
            result = grouped_product_search(
                group_by=group_by,
                in_scope=in_scope,
                matched_codes=matched_codes,
                spec_ids_by_group=self._spec_ids_by_group(
                    connection, in_scope, group_by, filter_spec_ids
                ),
                filter_spec_ids=filter_spec_ids,
                limit=limit,
                composite_excluded=composite_excluded,
                filters_applied=applied,
                families_not_found=missed,
                empty_hint=empty_hint,
            )
            sample_hits = [
                hit for group in result["groups"] for hit in group["sample_hits"]
            ]
            kept, dropped = self._shared_return_specs(kw, return_specs)
            self._attach_return_specs(connection, sample_hits, kept)
            if dropped:
                result["specs_not_shared"] = _not_shared_note(dropped, group_by)
            # After grouping, not before: `group_key` and `group_path` read the
            # per-hit family and path, and grouping by family is precisely the
            # case where they differ and nothing is hoisted.
            return hoist_scope(result, sample_hits, SEARCH_SCOPE_FIELDS)

        hits = [hit for hit in in_scope if hit["sku_code"] in matched_codes]
        total = len(hits)
        limited = hits[:limit]
        kept, dropped = self._shared_return_specs(kw, return_specs)
        self._attach_return_specs(connection, limited, kept)
        result = {
            "hits": limited,
            "total_matched": total,
            "composite_excluded": composite_excluded,
            "filters_applied": applied,
            "widening_hint": None if total else empty_hint,
        }
        if missed:
            result["families_not_found"] = missed
        if dropped:
            result["specs_not_shared"] = _not_shared_note(
                dropped, kw.get("group_by") or "family"
            )
        return hoist_scope(result, limited, SEARCH_SCOPE_FIELDS)

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
            # `fact_sentence` and `is_canonical_spec` are not selected. The
            # sentence is a template — "E-CSCS400DM4CO (New Changeover
            # Switches, 400 A, 4-pole) has a ambient / cubicle service
            # temperature of 40 °C." — and across 200,000 catalogue rows 87.9%
            # of them contain both the label and the value display verbatim,
            # while the rest are template variants carrying nothing the
            # neighbouring columns do not. It was 31.0% of this payload, and
            # not one of the 141 sentences in a captured run reached the report
            # or the answer. `is_canonical_spec` is read nowhere.
            #
            # `spec_label` is selected: 61% of the catalogue's distinct
            # (spec_id, spec_label) pairs cannot be recovered from the id, and
            # dropping it left the model reading `10_12` for "10, 12".
            facts = connection.execute(
                """
                SELECT spec_id, spec_label, unit, value_num,
                       value_min, value_max, value_display, value_kind,
                       source_of_truth, fact_source_pdf AS source_pdf,
                       fact_source_page AS source_page,
                       fact_source_heading AS source_heading
                FROM sku_fact
                WHERE sku_code = ? AND is_sentinel = 0 AND spec_id IS NOT NULL
                ORDER BY spec_id
                """,
                (resolved,),
            ).fetchall()
            result["facts"] = [compact_fact(dict(f)) for f in facts]
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
            chunk_limit = get_limits().max_chunk_chars
            result["chunks"] = [
                {
                    **dict(c),
                    "chunk_id": str(c["chunk_id"]),
                    "text": _clip(c["text"], chunk_limit),
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
                SELECT sku_code, price_status, price_quotable, price_inr,
                       price_sibling_code, price_observations
                FROM sku_fact WHERE sku_code = ? AND {_SKU_GRAIN}
                """,
                (resolved,),
            ).fetchone()
            observations = _loads(row["price_observations"], []) or []
            price: dict[str, Any] = {
                "sku_code": resolved,
                "price_status": row["price_status"],
                "price_inr": row["price_inr"],
                "observations": observations,
                "quotable": bool(row["price_quotable"]),
            }
            # The figure is publishable, but it was read from a pricelist table
            # headed by another product's code, so a sibling's price may have
            # been bound to it. Quote it only with this stated.
            if sibling := row["price_sibling_code"]:
                price["price_sibling_code"] = sibling
                price["caveat"] = (
                    f"This price was read from a pricelist table headed by "
                    f"{sibling}, a different ordering code. Report the figure "
                    "with that caveat and advise confirming it with C&S."
                )
            prices.append(price)
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
        peer_count = connection.execute(
            f"SELECT count(*) FROM sku_fact WHERE peer_group = ? AND {_SKU_GRAIN}",
            (anchor["peer_group"],),
        ).fetchone()[0]
        # Peer groups reach 1,183 members, and each carries a decoded ordering
        # code, so returning them all costs ~61k tokens — more than the whole
        # context window of the local models. A page is enough to see how the
        # group varies; product_search is the tool for finding a specific one.
        page = get_limits().max_peer_rows
        peers = connection.execute(
            f"""
            SELECT sku_code, family, decoded, price_status
            FROM sku_fact
            WHERE peer_group = ? AND {_SKU_GRAIN}
            ORDER BY sku_code
            LIMIT ?
            """,
            (anchor["peer_group"], page),
        ).fetchall()
        result = {
            "sku_code": resolved,
            "peer_group": anchor["peer_group"],
            "comparable_on": comparable,
            "related_codes": related,
            "peer_count": peer_count,
            "peers": [
                {
                    "sku_code": p["sku_code"],
                    "family": p["family"],
                    "price_status": p["price_status"],
                    **(
                        {"decoded": decoded}
                        if (decoded := flatten_decoded(_loads(p["decoded"], {})))
                        else {}
                    ),
                }
                for p in peers
            ],
        }
        # A peer group is inside one family by construction, so `family` was the
        # same string on all 25 rows; the decode was two thirds of the payload
        # before flattening.
        hoist_scope(result, result["peers"], PEER_SCOPE_FIELDS)
        if peer_count > len(result["peers"]):
            result["truncated"] = (
                f"Showing {len(result['peers'])} of {peer_count} peers, ordered by "
                "ordering code. The group is larger than this sample: use "
                "product_search with the family and a specific filter to reach a "
                "peer that is not listed, and never state the group has only "
                f"{len(result['peers'])} members."
            )
        return result

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
                }
            ]
        return self._search_documents_sqlite(kw)

    def _search_documents_sqlite(self, kw: dict[str, Any]) -> list[dict]:
        limit = max(1, min(int(kw.get("k", 6)), 20))
        text_limit = get_limits().max_chunk_chars
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
                # No `chunk_id` and no `mode`. The chunk id is a build-source
                # row number with no citation value and every appearance of it
                # in an answer would be a number the customer cannot look up;
                # `mode` is retrieval internals the model must not reason about.
                # A `distance` is still present on exactly the vector path, so
                # which scale `score` is on remains readable from the payload.
                deduped.append(
                    {
                        "text": _clip(row["text"], text_limit),
                        "chunk_type": row["chunk_type"],
                        "headings": _loads(row["headings"], []),
                        "sku_code": row["sku_code"],
                        "family": row["family"],
                        "distance": distance,
                        "score": 1.0 - distance,
                        "shared_by_sku_count": hash_counts.get(row["content_hash"], 1),
                        "brochure_md": row["brochure_md"],
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
                    "text": _clip(row["text"], text_limit),
                    "chunk_type": row["chunk_type"],
                    "headings": _loads(row["headings"], []),
                    "sku_code": row["sku_code"],
                    "family": row["family"],
                    "score": float(row["rank"]) if row["rank"] is not None else 0.0,
                    "shared_by_sku_count": 1,
                    "brochure_md": row["brochure_md"],
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
