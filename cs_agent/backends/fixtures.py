"""Synthetic JSON catalogue with an in-memory SQLite analytics boundary."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parents[1] / "data" / "fixtures"
_READ_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)

FACT_GROUP_MAP = {
    "electrical": {
        "rated_current_a",
        "poles",
        "icu_ka",
        "operational_current_a",
        "motor_power_kw",
        "coil_voltage_v",
    },
    "trip_units": {"trip_unit"},
    "accessories": {"aux_contacts"},
    "mechanical": set(),
    "dimensions": set(),
    "certifications": set(),
    "commercial": set(),
}


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

    def list_canonical_facts(self, category_path: str | None) -> list[dict]:
        facts = self._catalog["canonical_facts"]
        if category_path is None:
            return facts
        return [fact for fact in facts if fact["category"] == category_path]

    def taxonomy_browse(self, node_id: str | None, depth: int) -> dict:
        depth = max(1, min(depth, 2))
        categories = self._catalog["categories"]
        counts = {
            category["id"]: sum(
                1
                for family in self._catalog["families"]
                if family["category"] == category["id"]
            )
            for category in categories
        }

        def _children(prefix: str | None, remaining: int) -> list[dict[str, Any]]:
            if remaining <= 0:
                return []
            out: list[dict[str, Any]] = []
            for category in categories:
                cid = category["id"]
                if prefix is None:
                    top = cid.split("/", 1)[0]
                    if any(child["id"] == top for child in out):
                        continue
                    child_ids = [c["id"] for c in categories if c["id"].startswith(top)]
                    node = {
                        "id": top,
                        "name": top.title(),
                        "product_count": sum(counts[i] for i in child_ids),
                    }
                    if remaining > 1:
                        node["children"] = _children(top, remaining - 1)
                    out.append(node)
                elif cid.startswith(prefix + "/") or cid == prefix:
                    if cid == prefix:
                        continue
                    # Only direct children under prefix
                    rest = cid[len(prefix) + 1 :]
                    if "/" in rest and remaining == 1:
                        continue
                    direct = f"{prefix}/{rest.split('/', 1)[0]}"
                    if any(child["id"] == direct for child in out):
                        continue
                    meta = next((c for c in categories if c["id"] == direct), None)
                    node = {
                        "id": direct,
                        "name": meta["name"] if meta else direct,
                        "product_count": counts.get(direct, 0),
                    }
                    if remaining > 1 and meta:
                        node["children"] = []
                    out.append(node)
            return out

        return {
            "node_id": node_id,
            "children": _children(node_id, depth),
        }

    def product_search(
        self,
        *,
        category_path: str,
        filters: list[dict[str, Any]] | None = None,
        text: str | None = None,
        limit: int = 20,
    ) -> list[dict] | dict:
        filters = filters or []
        definitions = {
            fact["id"]: fact for fact in self.list_canonical_facts(category_path)
        }
        for item in filters:
            fact_id = item["canonical_fact_id"]
            if fact_id not in definitions:
                return {"error": f"Unknown canonical fact {fact_id!r} for {category_path}"}
            required = definitions[fact_id].get("condition_keys", [])
            provided = item.get("conditions") or {}
            missing = [key for key in required if key not in provided]
            if missing:
                return {"error": f"{fact_id} requires conditions: {missing}"}

        products = []
        for family in self._catalog["families"]:
            if family["category"] != category_path:
                continue
            if text:
                hay = f"{family['family_id']} {family['name']} {family['summary']}".lower()
                if text.lower() not in hay:
                    continue
            if all(self._matches(family, item) for item in filters):
                products.append(
                    {
                        "family_id": family["family_id"],
                        "name": family["name"],
                        "category": family["category"],
                        "summary": family["summary"],
                        "facts": family["facts"],
                    }
                )
            if len(products) >= limit:
                break
        return products

    def get_product(
        self, family_id: str, fact_groups: list[str], include_variants: bool
    ) -> dict:
        for family in self._catalog["families"]:
            if family["family_id"] != family_id:
                continue
            allowed_ids: set[str] = set()
            for group in fact_groups:
                allowed_ids |= FACT_GROUP_MAP.get(group, set())
            facts = [
                fact
                for fact in family["facts"]
                if not allowed_ids or fact["canonical_fact_id"] in allowed_ids
            ]
            result = {
                "family_id": family["family_id"],
                "name": family["name"],
                "category": family["category"],
                "summary": family["summary"],
                "facts": facts,
                "fact_groups": fact_groups,
            }
            if include_variants:
                result["variants"] = family["variants"]
            return result
        return {"error": f"Unknown product family {family_id!r}"}

    def search_documents(
        self,
        *,
        query: str,
        category_path: str | None = None,
        family_id: str | None = None,
        k: int = 6,
    ) -> list[dict]:
        if category_path is None and family_id is None:
            # Soft-guide unfiltered search: still search, but prefer filtered use.
            pass
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        ranked = []
        family_category = {
            family["family_id"]: family["category"]
            for family in self._catalog["families"]
        }
        for chunk in self._documents:
            if family_id and chunk["family_id"] != family_id:
                continue
            if category_path and family_category.get(chunk["family_id"]) != category_path:
                continue
            haystack = set(re.findall(r"[a-z0-9]+", chunk["text"].lower()))
            score = len(terms & haystack)
            if score:
                ranked.append((score, chunk))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["page"]))
        return [{**chunk, "score": score} for score, chunk in ranked[:k]]

    # SKU-centric fixture API. Each legacy variant is treated as a SKU carrying its
    # family's facts; this keeps offline graph tests useful while production uses Postgres.
    @staticmethod
    def _matches_text(value: Any, wanted: Any) -> bool:
        """Case-insensitive substring match, mirroring the Postgres ILIKE filters."""
        if wanted in (None, ""):
            return True
        return str(wanted).strip().lower() in str(value or "").lower()

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
                        "family": family["family_id"],
                        "category": family["category"],
                        "decoded": {},
                        "completeness": {"missing": []},
                        "facts": facts,
                    }
                )
        return skus

    def list_canonical_specs(self, category: str | None) -> list[dict]:
        rows = []
        for fact in self._catalog["canonical_facts"]:
            if not self._matches_text(fact["category"], category):
                continue
            values = [
                item["value_num"]
                for family in self._catalog["families"]
                if family["category"] == fact["category"]
                for item in family["facts"]
                if item["canonical_fact_id"] == fact["id"]
                and item["value_num"] is not None
            ]
            rows.append(
                {
                    "category": fact["category"],
                    "spec_id": fact["id"],
                    "spec_label": fact["name"],
                    "unit": fact["unit"],
                    "value_kind": (
                        "scalar" if fact["value_type"] == "number" else "text"
                    ),
                    "sku_count": sum(
                        len(family["variants"])
                        for family in self._catalog["families"]
                        if family["category"] == fact["category"]
                        and any(
                            item["canonical_fact_id"] == fact["id"]
                            for item in family["facts"]
                        )
                    ),
                    "observed_min": min(values) if values else None,
                    "observed_max": max(values) if values else None,
                }
            )
        return rows

    def taxonomy_browse(
        self, category: str | None = None, family: str | None = None
    ) -> dict:
        skus = self._fixture_skus()
        if category is None:
            names = sorted({sku["category"] for sku in skus})
            return {
                "level": "categories",
                "categories": [
                    {
                        "category": name,
                        "sku_count": sum(sku["category"] == name for sku in skus),
                    }
                    for name in names
                ],
            }
        if family is None:
            names = sorted(
                {
                    sku["family"]
                    for sku in skus
                    if self._matches_text(sku["category"], category)
                }
            )
            return {
                "level": "families",
                "category": category,
                "families": [
                    {
                        "family": name,
                        "sku_count": sum(sku["family"] == name for sku in skus),
                    }
                    for name in names
                ],
            }
        return {
            "level": "facets",
            "category": category,
            "family": family,
            "sku_count": sum(
                self._matches_text(sku["category"], category)
                and self._matches_text(sku["family"], family)
                for sku in skus
            ),
            "axes": {},
        }

    def product_search(self, **kw: Any) -> list[dict] | dict:
        hits = []
        for sku in self._fixture_skus():
            if not self._matches_text(sku["category"], kw.get("category")):
                continue
            if not self._matches_text(sku["family"], kw.get("family")):
                continue
            text = kw.get("text")
            if text and not any(
                self._matches_text(sku[field], text)
                for field in ("sku_code", "family", "category")
            ):
                continue
            matched = True
            for wanted in kw.get("filters") or []:
                candidates = [
                    fact
                    for fact in sku["facts"]
                    if self._matches_text(fact["spec_id"], wanted["spec_id"])
                ]
                if not candidates:
                    matched = False
                    break
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
                        and str(expected).lower()
                        in str(fact["value_display"]).lower()
                    )
                    for fact in candidates
                )
                if not matched:
                    break
            if matched:
                requested = set(kw.get("return_specs") or [])
                hits.append(
                    {
                        **{key: sku[key] for key in (
                            "sku_code", "family", "category", "completeness"
                        )},
                        "decoded_summary": sku["decoded"],
                        "price_display": None,
                        "specs": [
                            fact
                            for fact in sku["facts"]
                            if not requested
                            or any(
                                self._matches_text(fact["spec_id"], spec)
                                for spec in requested
                            )
                        ],
                    }
                )
            if len(hits) >= int(kw.get("limit", 20)):
                break
        return hits

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

    def get_sku(self, sku_code: str, include: list[str]) -> dict:
        sku = self._resolve_sku(sku_code)
        if not sku:
            return {"error": f"No SKU matches {sku_code!r}"}
        result = {
            key: sku[key]
            for key in ("sku_code", "family", "category", "completeness")
        }
        if "facts" in include:
            result["facts"] = sku["facts"]
        if "decoded" in include:
            result["decoded"] = sku["decoded"]
        if "sources" in include:
            result["sources"] = ["synthetic fixture"]
        if "content" in include:
            result["content"] = [
                chunk
                for chunk in self._documents
                if chunk["family_id"] == sku["family"]
            ]
        return result

    def compare_skus(
        self, sku_codes: list[str], spec_ids: list[str] | None = None
    ) -> dict:
        selected: list[dict[str, Any]] = []
        unresolved: list[str] = []
        for requested in sku_codes:
            match = self._resolve_sku(requested)
            if match is None:
                unresolved.append(requested)
            elif match not in selected:
                selected.append(match)
        sku_codes = [sku["sku_code"] for sku in selected]
        available = sorted(
            {fact["spec_id"] for sku in selected for fact in sku["facts"]}
        )
        ids = (
            [
                spec
                for spec in available
                if any(self._matches_text(spec, wanted) for wanted in spec_ids)
            ]
            if spec_ids
            else available
        )
        rows = []
        for spec_id in ids:
            matching = {
                sku["sku_code"]: next(
                    (
                        fact
                        for fact in sku["facts"]
                        if fact["spec_id"] == spec_id
                    ),
                    None,
                )
                for sku in selected
            }
            sample = next((fact for fact in matching.values() if fact), {})
            rows.append(
                {
                    "spec_id": spec_id,
                    "spec_label": sample.get("spec_label"),
                    "unit": sample.get("unit"),
                    "values": {
                        code: (
                            matching.get(code, {}).get("value_display")
                            if matching.get(code)
                            else None
                        )
                        for code in sku_codes
                    },
                    "facts": [fact for fact in matching.values() if fact],
                }
            )
        result: dict[str, Any] = {"sku_codes": sku_codes, "rows": rows}
        if unresolved:
            result["unresolved_sku_codes"] = unresolved
        return result

    def search_documents(
        self,
        *,
        query: str,
        category: str | None = None,
        family: str | None = None,
        sku_code: str | None = None,
        k: int = 6,
    ) -> list[dict]:
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        sku = self._resolve_sku(sku_code) if sku_code else None
        if sku_code and not sku:
            return []
        wanted_family = family or (sku["family"] if sku else None)
        categories = {
            item["family"]: item["category"] for item in self._fixture_skus()
        }
        ranked = []
        for chunk in self._documents:
            if not self._matches_text(chunk["family_id"], wanted_family):
                continue
            if not self._matches_text(categories.get(chunk["family_id"]), category):
                continue
            score = len(terms & set(re.findall(r"[a-z0-9]+", chunk["text"].lower())))
            if score:
                ranked.append((score, chunk))
        ranked.sort(key=lambda pair: -pair[0])
        return [
            {
                "text": chunk["text"],
                "family": chunk["family_id"],
                "sku_code": sku["sku_code"] if sku else None,
                "score": score,
                "shared_by_sku_count": 1,
            }
            for score, chunk in ranked[:k]
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

    @staticmethod
    def _matches(family: dict[str, Any], wanted: dict[str, Any]) -> bool:
        candidates = [
            fact
            for fact in family["facts"]
            if fact["canonical_fact_id"] == wanted["canonical_fact_id"]
            and all(
                fact.get("conditions", {}).get(key) == value
                for key, value in (wanted.get("conditions") or {}).items()
            )
        ]
        operator = wanted.get("op", wanted.get("operator", "eq"))
        expected = wanted.get("value")
        if expected is None:
            expected = wanted.get("value_num")
            if expected is None:
                expected = wanted.get("value_text")
        for fact in candidates:
            actual = fact["value_num"]
            if actual is None:
                actual = fact["value_text"]
            if operator == "eq" and actual == expected:
                return True
            if operator == "gte" and actual is not None and actual >= expected:
                return True
            if operator == "lte" and actual is not None and actual <= expected:
                return True
            if operator == "in" and actual in (expected or []):
                return True
            if operator == "contains" and str(expected).lower() in str(actual).lower():
                return True
        return False

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
