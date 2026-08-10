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
