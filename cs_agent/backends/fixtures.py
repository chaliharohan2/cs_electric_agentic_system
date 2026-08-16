"""Synthetic JSON catalogue with an in-memory SQLite analytics boundary."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from cs_agent.backends.matching import matches

DATA_DIR = Path(__file__).parents[1] / "data" / "fixtures"
_READ_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


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
                        "market_segments": [],
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
                    for key in (
                        "sku_code", "canonical_code", "family", "description"
                    )
                } | {
                    "path_text": " > ".join(sku["path"]),
                    "match_role": "sku" if exact else "description",
                    "score": 1.0 if exact else 0.5,
                }
                for sku in candidates[: int(kw.get("limit", 8))]
            ],
        }

    def list_canonical_specs(self, **kw: Any) -> list[dict]:
        family_filter = kw.get("family")
        contains = (kw.get("spec_id_contains") or "").lower()
        rows: dict[tuple[str, str], dict[str, Any]] = {}
        for sku in self._fixture_skus():
            if not self._matches_text(sku["family"], family_filter):
                continue
            for fact in sku["facts"]:
                if contains and contains not in fact["spec_id"].lower():
                    continue
                key = (sku["family"], fact["spec_id"])
                row = rows.setdefault(key, {
                    "family": sku["family"],
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
        return list(rows.values())

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

    def product_search(self, **kw: Any) -> dict:
        hits: list[dict[str, Any]] = []
        numeric_filters = [
            item for item in kw.get("filters") or []
            if item["op"] in {"gte", "lte", "eq"}
        ]
        for sku in self._fixture_skus():
            path = kw.get("path") or []
            if path and sku["path"][:len(path)] != path:
                continue
            if not self._matches_text(sku["family"], kw.get("family")):
                continue
            text = kw.get("text")
            if text and not self._matches_text(
                f"{sku['sku_code']} {sku['family']} {sku['description']}", text
            ):
                continue
            matched = True
            for wanted in kw.get("filters") or []:
                candidates = [
                    fact for fact in sku["facts"]
                    if fact["spec_id"] == wanted["spec_id"]
                ]
                op, expected = wanted["op"], wanted["value"]
                matched = any(
                    (op == "eq" and fact["value_num"] == expected)
                    or (op == "gte" and fact["value_num"] is not None and fact["value_num"] >= expected)
                    or (op == "lte" and fact["value_num"] is not None and fact["value_num"] <= expected)
                    or (op == "contains" and str(expected).lower() in fact["value_display"].lower())
                    for fact in candidates
                )
                if not matched:
                    break
            if matched:
                requested = set(kw.get("return_specs") or [])
                hits.append({
                    **{key: sku[key] for key in (
                        "sku_code", "canonical_code", "family", "path",
                        "description", "url", "price_status", "decoded"
                    )},
                    "specs": [
                        fact for fact in sku["facts"]
                        if not requested or fact["spec_id"] in requested
                    ],
                })
        total = len(hits)
        limit = int(kw.get("limit", 20))
        return {
            "hits": hits[:limit],
            "total_matched": total,
            "composite_excluded": 0 if numeric_filters else 0,
            "filters_applied": [
                f"{item['spec_id']} {item['op']} {item['value']}"
                for item in kw.get("filters") or []
            ],
            "widening_hint": None if total else "Broaden the path, family, or specification filter.",
        }

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
            result["facts"] = sku["facts"]
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
            {"sku_code": item["sku_code"], "family": item["family"], "decoded": item["decoded"],
             "price_status": item["price_status"]}
            for item in self._fixture_skus() if item["peer_group"] == sku["peer_group"]
        ]
        # peer_count mirrors the SQLite backend, which pages large groups; the
        # fixture set is small enough that the page is always the whole group.
        return {
            "sku_code": sku["sku_code"],
            "peer_group": sku["peer_group"],
            "comparable_on": sku["comparable_on"],
            "related_codes": sku["related_codes"],
            "peer_count": len(peers),
            "peers": peers,
        }

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
                "shared_by_sku_count": 1, "mode": "lexical",
            }
            for score, chunk, matched in ranked[: int(kw.get("k", 6))]
        ]

    def execute_sql(self, sql: str) -> dict[str, Any]:
        statement = sql.strip().rstrip(";")
        if not _READ_ONLY.match(statement) or ";" in statement:
            return {"error": "Only one read-only SELECT statement is allowed"}
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
