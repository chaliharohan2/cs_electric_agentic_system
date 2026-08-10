"""Backend boundary for product catalogue data."""

from __future__ import annotations

from typing import Any, Protocol


class CatalogBackend(Protocol):
    def list_canonical_facts(self, category_path: str | None) -> list[dict]:
        """Return fact definitions: id, unit, value_type, condition_keys, category."""

    def taxonomy_browse(self, node_id: str | None, depth: int) -> dict:
        """Return taxonomy node with children and product_count per child."""

    def product_search(self, **kw: Any) -> list[dict] | dict:
        """Return matching families, or ``{"error": ...}`` on invalid filters."""

    def get_product(
        self, family_id: str, fact_groups: list[str], include_variants: bool
    ) -> dict:
        """Return one family with grouped facts (and variants if requested)."""

    def search_documents(self, **kw: Any) -> list[dict]:
        """Return brochure chunks with doc/page/text metadata."""

    def execute_sql(self, sql: str) -> dict:
        """Return ``{"columns": [...], "rows": [...]}`` or ``{"error": ...}``."""
