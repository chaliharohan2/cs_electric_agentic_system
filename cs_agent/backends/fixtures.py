"""Synthetic JSON catalogue with an in-memory SQLite analytics boundary."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

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

    def list_categories(self) -> list[dict[str, Any]]:
        return self._catalog["categories"]

    def list_facts(self, category: str) -> list[dict[str, Any]]:
        return [
            fact
            for fact in self._catalog["canonical_facts"]
            if fact["category"] == category
        ]

    def product_search(
        self, category: str, filters: list[dict[str, Any]]
    ) -> dict[str, Any]:
        definitions = {fact["id"]: fact for fact in self.list_facts(category)}
        for item in filters:
            fact_id = item["canonical_fact_id"]
            if fact_id not in definitions:
                return {"error": f"Unknown canonical fact {fact_id!r} for {category}"}
            required = definitions[fact_id].get("condition_keys", [])
            missing = [
                key for key in required if key not in (item.get("conditions") or {})
            ]
            if missing:
                return {
                    "error": (
                        f"{fact_id} requires conditions: {missing}"
                    )
                }

        products = []
        for family in self._catalog["families"]:
            if family["category"] != category:
                continue
            if all(self._matches(family, item) for item in filters):
                products.append(family)
        return {"products": products, "count": len(products)}

    def get_product(self, family_id: str) -> dict[str, Any]:
        for family in self._catalog["families"]:
            if family["family_id"] == family_id:
                return family
        return {"error": f"Unknown product family {family_id!r}"}

    def search_documents(
        self, query: str, family_id: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        ranked = []
        for chunk in self._documents:
            if family_id and chunk["family_id"] != family_id:
                continue
            haystack = set(re.findall(r"[a-z0-9]+", chunk["text"].lower()))
            score = len(terms & haystack)
            if score:
                ranked.append((score, chunk))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["page"]))
        return [{**chunk, "score": score} for score, chunk in ranked[:limit]]

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
        operator = wanted.get("operator", "eq")
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
