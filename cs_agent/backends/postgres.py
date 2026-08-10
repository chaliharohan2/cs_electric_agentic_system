"""Future PostgreSQL catalogue adapter — schema not yet available."""

from __future__ import annotations

from typing import Any


class PostgresBackend:
    def list_canonical_facts(self, category_path: str | None) -> list[dict]:
        """Return fact definitions with id, unit, value_type, condition_keys."""
        raise NotImplementedError("SCHEMA_PENDING")

    def taxonomy_browse(self, node_id: str | None, depth: int) -> dict:
        """Return ``{"node_id", "children": [{"id", "name", "product_count", ...}]}``."""
        raise NotImplementedError("SCHEMA_PENDING")

    def product_search(self, **kw: Any) -> list[dict] | dict:
        """Return a list of family summaries matching filters, or an error mapping."""
        raise NotImplementedError("SCHEMA_PENDING")

    def get_product(
        self, family_id: str, fact_groups: list[str], include_variants: bool
    ) -> dict:
        """Return family detail with facts grouped by area and optional variants."""
        raise NotImplementedError("SCHEMA_PENDING")

    def search_documents(self, **kw: Any) -> list[dict]:
        """Return ranked chunks: family_id, doc, page, text, score."""
        raise NotImplementedError("SCHEMA_PENDING")

    def execute_sql(self, sql: str) -> dict:
        """Return read-only query results as columns and rows."""
        raise NotImplementedError("SCHEMA_PENDING")
