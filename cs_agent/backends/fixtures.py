"""Synthetic JSON catalogue with an in-memory SQLite analytics boundary."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from cs_agent.backends.grouped_search import (
    GROUP_BY_SCOPE_ERROR,
    grouped_product_search,
    group_key,
    has_search_scope,
)
from cs_agent.backends.matching import family_matches, matches, unmatched_family_terms
from cs_agent.backends.payload_shape import (
    PEER_SCOPE_FIELDS,
    SEARCH_SCOPE_FIELDS,
    flatten_decoded,
    hoist_scope,
)
from cs_agent.backends.path_levels import NA, path_to_levels
from cs_agent.backends.read_only_sql import read_only_sql_error
from cs_agent.backends.sqlite import _not_shared_note
from cs_agent.backends.spec_envelope import (
    NESTED_REDUNDANT,
    compact_fact,
    group_specs,
)

DATA_DIR = Path(__file__).parents[1] / "data" / "fixtures"


class FixturesBackend:
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self._catalog = json.loads(
            (data_dir / "catalog.json").read_text(encoding="utf-8")
        )
        self._documents = json.loads(
            (data_dir / "documents.json").read_text(encoding="utf-8")
        )
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._build_analytics_db()

    @staticmethod
    def _matches_text(value: Any, wanted: Any) -> bool:
        """Delegate to the shared punctuation-tolerant catalogue matcher."""
        return matches(value, wanted)

    def _fixture_skus(self) -> list[dict[str, Any]]:
        skus = []
        for family in self._catalog["families"]:
            facts = [
                {
                    "spec_id": fact["canonical_fact_id"],
                    "spec_label": fact["canonical_fact_id"].replace("_", " ").title(),
                    "unit": fact["unit"],
                    "value_num": fact["value_num"],
                    "value_min": None,
                    "value_max": None,
                    "value_display": str(
                        fact["value_num"]
                        if fact["value_num"] is not None
                        else fact["value_text"]
                    ),
                    "value_kind": (
                        "scalar" if fact["value_num"] is not None else "text"
                    ),
                    "source_of_truth": "fixture",
                    "derived": False,
                    "fact_sentence": None,
                }
                for fact in family["facts"]
            ]
            for code in family["variants"]:
                skus.append(
                    {
                        "sku_code": code,
                        "canonical_code": code,
                        "family": family["family_id"],
                        "category": family["category"],
                        "path": [*family["category"].split("/"), family["family_id"]],
                        "description": family["summary"],
                        "url": None,
                        "price_status": "not_listed",
                        "peer_group": family["family_id"],
                        "comparable_on": [fact["spec_id"] for fact in facts],
                        "related_codes": family["variants"],
                        "market_segments": list(family.get("market_segments") or []),
                        "also_published_as": [],
                        "decoded": {},
                        "extraction": {"missing": [], "confidence": "fixture"},
                        "facts": facts,
                    }
                )
        return skus

    def _resolve_sku(self, sku_code: str) -> dict[str, Any] | None:
        skus = self._fixture_skus()
        exact = next(
            (
                item
                for item in skus
                if item["sku_code"].lower() == str(sku_code).strip().lower()
            ),
            None,
        )
        if exact:
            return exact
        return next(
            (item for item in skus if self._matches_text(item["sku_code"], sku_code)),
            None,
        )

    # Catalogue API mirroring the production tool envelopes,
    # built from the compact synthetic source data.
    def resolve_product(self, **kw: Any) -> dict:
        query = str(kw["query"])
        family_hint = kw.get("family_hint")
        exact = [
            sku for sku in self._fixture_skus()
            if re.sub(r"[^a-z0-9]", "", sku["sku_code"].lower())
            == re.sub(r"[^a-z0-9]", "", query.lower())
            and self._matches_text(sku["family"], family_hint)
        ]
        candidates = exact or [
            sku for sku in self._fixture_skus()
            if self._matches_text(
                f"{sku['sku_code']} {sku['family']} {sku['description']}", query
            )
            and self._matches_text(sku["family"], family_hint)
        ]
        return {
            "resolution": "exact" if exact else "descriptive",
            "hits": [
                {
                    key: sku[key]
                    for key in ("sku_code", "family", "description")
                } | {
                    "path_text": " > ".join(sku["path"]),
                    "match_role": "sku" if exact else "description",
                    "score": 1.0 if exact else 0.5,
                }
                for sku in candidates[: int(kw.get("limit", 8))]
            ],
        }

    def _scoped_skus(self, path: list[str], family_filter: Any) -> list[dict[str, Any]]:
        return [
            sku
            for sku in self._fixture_skus()
            if (not path or sku["path"][: len(path)] == path)
            and family_matches(sku["family"], family_filter)
        ]

    def _groups_in_scope(self, path: list[str], family_filter: Any, group_by: str) -> list[str]:
        groups = set()
        for sku in self._scoped_skus(path, family_filter):
            if group_by == "family":
                groups.add(sku["family"])
                continue
            value = path_to_levels(sku["path"]).get(group_by)
            if value and value != NA:
                groups.add(value)
        return sorted(groups)

    def spec_rows(self, **kw: Any) -> list[dict[str, Any]]:
        family_filter = kw.get("family")
        path = list(kw.get("path") or [])
        contains = (kw.get("spec_id_contains") or "").lower()
        canonical_only = bool(kw.get("canonical_only"))
        rows: dict[tuple[str, str], dict[str, Any]] = {}
        for sku in self._fixture_skus():
            if path and sku["path"][: len(path)] != path:
                continue
            if not family_matches(sku["family"], family_filter):
                continue
            for fact in sku["facts"]:
                if contains and contains not in fact["spec_id"].lower() and contains not in (
                    fact.get("spec_label") or ""
                ).lower():
                    continue
                if canonical_only and not fact.get("is_canonical_spec", True):
                    continue
                key = (sku["family"], fact["spec_id"])
                row = rows.setdefault(key, {
                    "family": sku["family"],
                    "_path": sku["path"],
                    "spec_id": fact["spec_id"],
                    "spec_label": fact["spec_label"],
                    "unit": fact["unit"],
                    "value_kind": fact["value_kind"],
                    "is_canonical_spec": True,
                    "sku_count": 0,
                    "composite_count": 0,
                    "observed_min": None,
                    "observed_max": None,
                })
                row["sku_count"] += 1
                value = fact["value_num"]
                if value is not None:
                    row["observed_min"] = value if row["observed_min"] is None else min(row["observed_min"], value)
                    row["observed_max"] = value if row["observed_max"] is None else max(row["observed_max"], value)
        for row in rows.values():
            row.update(path_to_levels(row.pop("_path", []) or []))
        return list(rows.values())

    def list_canonical_specs(self, **kw: Any) -> dict:
        family_filter = kw.get("family")
        path = list(kw.get("path") or [])
        group_by = kw.get("group_by") or "family"
        result = group_specs(
            [compact_fact(row) for row in self.spec_rows(**kw)],
            groups=self._groups_in_scope(path, family_filter, group_by),
            group_by=group_by,
            path=path or None,
            family=family_filter,
        )
        missed = unmatched_family_terms(
            family_filter,
            [family["family_id"] for family in self._catalog["families"]],
        )
        if missed:
            result["families_not_found"] = missed
        return result

    def catalogue_map(self, **kw: Any) -> dict:
        path_text = (kw.get("path_text") or "").strip()
        market_segment = (kw.get("market_segment") or "").strip()
        limit = max(1, min(int(kw.get("limit", 40)), 100))

        branches: dict[str, dict[str, Any]] = {}
        for sku in self._fixture_skus():
            key = " > ".join(sku["path"])
            if key not in branches:
                # Same level columns the SQLite artifact groups on, so a fixture
                # test exercises the shape the live backend returns.
                named = {
                    column: value
                    for column, value in path_to_levels(sku["path"]).items()
                    if value != NA
                }
                branches[key] = {
                    **named,
                    "family": sku["path"][-1] if sku["path"] else sku["family"],
                    "path": list(sku["path"]),
                    "sku_count": 0,
                    "description": sku["description"],
                    "url": sku["url"],
                    "market_segments": list(sku.get("market_segments") or []),
                }
            branches[key]["sku_count"] += 1

        matched = [
            branch for key, branch in sorted(branches.items())
            if (not path_text or self._matches_text(key, path_text))
            and (
                not market_segment
                or any(
                    self._matches_text(segment, market_segment)
                    for segment in branch["market_segments"]
                )
            )
        ]
        matched.sort(key=lambda b: (-b["sku_count"], b["family"]))
        result: dict[str, Any] = {
            "groups": matched[:limit],
            "total_groups": len(matched),
            "total_skus": sum(branch["sku_count"] for branch in matched),
        }
        if market_segment:
            result["matched_on"] = {"market_segment": market_segment}
        if not matched:
            miss: dict[str, Any] = {}
            if path_text:
                miss["closest_paths"] = sorted(branches)[:6]
            if market_segment:
                miss["known_market_segments"] = sorted({
                    segment for branch in branches.values()
                    for segment in branch["market_segments"]
                })
            result["no_match"] = miss
        return result

    def taxonomy_browse(self, **kw: Any) -> dict:
        path = kw.get("path") or []
        children: dict[str, dict[str, Any]] = {}
        for sku in self._fixture_skus():
            if sku["path"][:len(path)] != path or len(sku["path"]) <= len(path):
                continue
            name = sku["path"][len(path)]
            item = children.setdefault(name, {
                "name": name,
                "sku_count": 0,
                "is_leaf": len(sku["path"]) == len(path) + 1,
                "description": sku["description"] if len(sku["path"]) == len(path) + 1 else None,
                "url": sku["url"],
            })
            item["sku_count"] += 1
        result: dict[str, Any] = {
            "path": path,
            "children": [item for name, item in sorted(children.items()) if name != "_no_category"],
            "uncategorised": {
                "children": [item for name, item in sorted(children.items()) if name == "_no_category"],
                "note": "These are pricelist section names, not published C&S categories.",
            },
        }
        if kw.get("include_facets") and path:
            result["facets"] = []
        return result

    def _sku_in_product_scope(self, sku: dict[str, Any], kw: dict[str, Any]) -> bool:
        path = kw.get("path") or []
        if path and sku["path"][: len(path)] != list(path):
            return False
        if not family_matches(sku["family"], kw.get("family")):
            return False
        text = kw.get("text")
        if text and not self._matches_text(
            f"{sku['sku_code']} {sku['family']} {sku['description']}", text
        ):
            return False
        segment = kw.get("market_segment")
        if segment and not any(
            self._matches_text(item, segment)
            for item in sku.get("market_segments") or []
        ):
            return False
        statuses = kw.get("price_status")
        if isinstance(statuses, str):
            statuses = [statuses]
        if statuses and sku.get("price_status") not in statuses:
            return False
        return True

    def _sku_matches_filters(
        self, sku: dict[str, Any], filters: list[dict[str, Any]]
    ) -> bool:
        for wanted in filters:
            candidates = [
                fact for fact in sku["facts"] if fact["spec_id"] == wanted["spec_id"]
            ]
            op, expected = wanted["op"], wanted["value"]
            matched = any(
                (op == "eq" and fact["value_num"] == expected)
                or (
                    op == "gte"
                    and fact["value_num"] is not None
                    and fact["value_num"] >= expected
                )
                or (
                    op == "lte"
                    and fact["value_num"] is not None
                    and fact["value_num"] <= expected
                )
                or (
                    op == "contains"
                    and str(expected).lower() in fact["value_display"].lower()
                )
                for fact in candidates
            )
            if not matched:
                return False
        return True

    def _hit_from_sku(
        self, sku: dict[str, Any], kw: dict[str, Any],
        return_specs: list[str] | None = None,
    ) -> dict[str, Any]:
        requested = set(
            kw.get("return_specs") or [] if return_specs is None else return_specs
        )
        return {
            **{
                key: sku[key]
                for key in (
                    "sku_code",
                    "family",
                    "path",
                    "description",
                    "url",
                    "price_status",
                )
            },
            **(
                {"decoded": decoded}
                if (decoded := flatten_decoded(sku["decoded"]))
                else {}
            ),
            "specs": [
                compact_fact(fact, drop=(*NESTED_REDUNDANT, "spec_label"))
                for fact in sku["facts"]
                if not requested or fact["spec_id"] in requested
            ],
        }

    def _shared_return_specs(
        self, kw: dict[str, Any], return_specs: list[str]
    ) -> tuple[list[str], dict[str, list[str]]]:
        group_by = kw.get("group_by") or "family"
        path = list(kw.get("path") or [])
        groups = self._groups_in_scope(path, kw.get("family"), group_by)
        if len(groups) <= 1 or not return_specs:
            return list(return_specs), {}
        holders: dict[str, set[str]] = {}
        for sku in self._scoped_skus(path, kw.get("family")):
            key = (
                sku["family"]
                if group_by == "family"
                else path_to_levels(sku["path"]).get(group_by)
            )
            for fact in sku["facts"]:
                if fact["spec_id"] in return_specs:
                    holders.setdefault(fact["spec_id"], set()).add(str(key))
        wanted = set(groups)
        kept, dropped = [], {}
        for spec_id in return_specs:
            held = holders.get(spec_id, set()) & wanted
            (kept.append(spec_id) if held == wanted else dropped.__setitem__(spec_id, sorted(held)))
        return kept, dropped

    def product_search(self, **kw: Any) -> dict:
        group_by = kw.get("group_by")
        if group_by and not has_search_scope(kw.get("path"), kw.get("family")):
            return {"error": GROUP_BY_SCOPE_ERROR}
        filters = list(kw.get("filters") or [])
        numeric_filters = [item for item in filters if item["op"] in {"gte", "lte", "eq"}]
        in_scope = [
            sku for sku in self._fixture_skus() if self._sku_in_product_scope(sku, kw)
        ]
        matched_skus = [
            sku for sku in in_scope if self._sku_matches_filters(sku, filters)
        ]
        applied = [
            f"{item['spec_id']} {item['op']} {item['value']}" for item in filters
        ]
        missed = unmatched_family_terms(
            kw.get("family"),
            [family["family_id"] for family in self._catalog["families"]],
        )
        kept, dropped = self._shared_return_specs(kw, list(kw.get("return_specs") or []))
        if group_by:
            in_scope_hits = [self._hit_from_sku(sku, kw, kept) for sku in in_scope]
            spec_ids_by_group: dict[str, set[str]] = {}
            filter_spec_ids = [item["spec_id"] for item in filters]
            if filter_spec_ids:
                for sku, hit in zip(in_scope, in_scope_hits, strict=True):
                    key = group_key(hit, group_by)
                    published = spec_ids_by_group.setdefault(key, set())
                    for fact in sku["facts"]:
                        published.add(fact["spec_id"])
            result = grouped_product_search(
                group_by=group_by,
                in_scope=in_scope_hits,
                matched_codes={sku["sku_code"] for sku in matched_skus},
                spec_ids_by_group=spec_ids_by_group,
                filter_spec_ids=filter_spec_ids,
                limit=int(kw.get("limit", 20)),
                composite_excluded=0 if numeric_filters else 0,
                filters_applied=applied,
                families_not_found=missed,
                empty_hint="Broaden the path, family, or specification filter.",
            )
            if dropped:
                result["specs_not_shared"] = _not_shared_note(dropped, group_by)
            sample_hits = [
                hit for group in result["groups"] for hit in group["sample_hits"]
            ]
            return hoist_scope(result, sample_hits, SEARCH_SCOPE_FIELDS)
        hits = [self._hit_from_sku(sku, kw, kept) for sku in matched_skus]
        total = len(hits)
        limit = int(kw.get("limit", 20))
        result = {
            "hits": hits[:limit],
            "total_matched": total,
            "composite_excluded": 0 if numeric_filters else 0,
            "filters_applied": applied,
            "widening_hint": None if total else "Broaden the path, family, or specification filter.",
        }
        if missed:
            result["families_not_found"] = missed
        if dropped:
            result["specs_not_shared"] = _not_shared_note(
                dropped, kw.get("group_by") or "family"
            )
        return hoist_scope(result, result["hits"], SEARCH_SCOPE_FIELDS)

    def get_sku(self, sku_code: str, include: list[str], **kw: Any) -> dict:
        sku = self._resolve_sku(sku_code)
        if not sku:
            return {"error": f"No ordering code resolves from {sku_code!r}"}
        result = {
            key: sku[key] for key in (
                "sku_code", "canonical_code", "family", "path", "description",
                "url", "price_status", "peer_group", "comparable_on",
                "related_codes", "extraction"
            )
        }
        if "facts" in include:
            # The same three keys the SQLite backend stopped selecting, dropped
            # here so a fixture test sees the shape the live backend returns.
            result["facts"] = [
                {
                    key: value
                    for key, value in fact.items()
                    if key not in ("spec_label", "fact_sentence", "is_canonical_spec")
                }
                for fact in sku["facts"]
            ]
        if "decoded" in include:
            result["decoded"] = sku["decoded"]
        if "sources" in include:
            result["sources"] = [{"ref_type": "other", "ref_name": "synthetic fixture", "page": None}]
        if "chunks" in include:
            result["chunks"] = [
                {**chunk, "mode": "lexical"}
                for chunk in self._documents
                if chunk["family_id"] == sku["family"]
            ]
        if "price" in include:
            result["price"] = self.get_price_detail([sku["sku_code"]])["prices"][0]
        if "peers" in include:
            result["peers"] = self.get_peer_group(sku["sku_code"])
        return result

    def get_price_detail(self, sku_codes: list[str]) -> dict:
        prices = []
        for code in sku_codes:
            sku = self._resolve_sku(code)
            prices.append(
                {"sku_code": sku["sku_code"], "price_status": "not_listed",
                 "observations": [], "quotable": False}
                if sku else {"sku_code": code, "error": "unresolved"}
            )
        return {"prices": prices}

    def get_peer_group(self, sku_code: str) -> dict:
        sku = self._resolve_sku(sku_code)
        if not sku:
            return {"error": f"No ordering code resolves from {sku_code!r}"}
        peers = [
            {"sku_code": item["sku_code"], "family": item["family"],
             "price_status": item["price_status"],
             **({"decoded": d} if (d := flatten_decoded(item["decoded"])) else {})}
            for item in self._fixture_skus() if item["peer_group"] == sku["peer_group"]
        ]
        # peer_count mirrors the SQLite backend, which pages large groups; the
        # fixture set is small enough that the page is always the whole group.
        result = {
            "sku_code": sku["sku_code"],
            "peer_group": sku["peer_group"],
            "comparable_on": sku["comparable_on"],
            "related_codes": sku["related_codes"],
            "peer_count": len(peers),
            "peers": peers,
        }
        return hoist_scope(result, peers, PEER_SCOPE_FIELDS)

    def compare_skus(
        self, sku_codes: list[str], spec_ids: list[str] | None = None
    ) -> dict:
        selected = [self._resolve_sku(code) for code in sku_codes]
        unresolved = [code for code, sku in zip(sku_codes, selected, strict=True) if not sku]
        selected = [sku for sku in selected if sku]
        axes = spec_ids or sorted({fact["spec_id"] for sku in selected for fact in sku["facts"]})
        rows = {
            axis: {
                sku["sku_code"]: next(
                    (fact["value_display"] for fact in sku["facts"] if fact["spec_id"] == axis),
                    None,
                )
                for sku in selected
            }
            for axis in axes
        }
        groups = {sku["peer_group"] for sku in selected}
        return {
            "sku_codes": [sku["sku_code"] for sku in selected],
            "axes": axes,
            "rows": rows,
            "peer_group_match": len(groups) == 1,
            "axes_source": "comparable_on" if not spec_ids and len(groups) == 1 else "union",
            "unresolved_sku_codes": unresolved,
        }

    def search_documents(self, **kw: Any) -> list[dict]:
        terms = set(re.findall(r"[a-z0-9]+", kw["query"].lower()))
        sku = self._resolve_sku(kw.get("sku_code")) if kw.get("sku_code") else None
        path = kw.get("path") or []
        ranked = []
        for chunk in self._documents:
            matching_sku = next(
                (item for item in self._fixture_skus() if item["family"] == chunk["family_id"]),
                None,
            )
            if not matching_sku:
                continue
            if path and matching_sku["path"][:len(path)] != path:
                continue
            if not self._matches_text(chunk["family_id"], kw.get("family") or (sku["family"] if sku else None)):
                continue
            score = len(terms & set(re.findall(r"[a-z0-9]+", chunk["text"].lower())))
            if score:
                ranked.append((score, chunk, matching_sku))
        ranked.sort(key=lambda item: -item[0])
        return [
            {
                "text": chunk["text"], "family": chunk["family_id"],
                "sku_code": sku["sku_code"] if sku else matched["sku_code"],
                "chunk_type": chunk.get("chunk_type", "features"),
                "headings": None, "brochure_md": None, "score": score,
                "shared_by_sku_count": 1,
            }
            for score, chunk, matched in ranked[: int(kw.get("k", 6))]
        ]

    def execute_sql(self, sql: str) -> dict[str, Any]:
        statement = sql.strip().rstrip(";")
        error = read_only_sql_error(statement)
        if error:
            return {"error": error}
        try:
            cursor = self._db.execute(statement)
            columns = [description[0] for description in cursor.description or []]
            return {
                "columns": columns,
                "rows": [dict(row) for row in cursor.fetchall()],
            }
        except sqlite3.Error as exc:
            return {"error": str(exc)}
    def _build_analytics_db(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE families (
                family_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                summary TEXT NOT NULL
            );
            CREATE TABLE variants (
                variant_id TEXT PRIMARY KEY,
                family_id TEXT NOT NULL
            );
            CREATE TABLE facts (
                family_id TEXT NOT NULL,
                canonical_fact_id TEXT NOT NULL,
                value_num REAL,
                value_text TEXT,
                unit TEXT,
                conditions_json TEXT NOT NULL
            );
            """
        )
        for family in self._catalog["families"]:
            self._db.execute(
                "INSERT INTO families VALUES (?, ?, ?, ?)",
                (
                    family["family_id"],
                    family["category"],
                    family["name"],
                    family["summary"],
                ),
            )
            self._db.executemany(
                "INSERT INTO variants VALUES (?, ?)",
                [(variant, family["family_id"]) for variant in family["variants"]],
            )
            self._db.executemany(
                "INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        family["family_id"],
                        fact["canonical_fact_id"],
                        fact["value_num"],
                        fact["value_text"],
                        fact["unit"],
                        json.dumps(fact["conditions"], sort_keys=True),
                    )
                    for fact in family["facts"]
                ],
            )
        self._db.commit()
