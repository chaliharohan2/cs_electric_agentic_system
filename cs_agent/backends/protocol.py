"""Backend boundary for product catalogue data."""

from __future__ import annotations

from typing import Any, Protocol


class CatalogBackend(Protocol):
    def list_canonical_specs(self, category: str | None) -> list[dict]:
        """Return observed specification definitions and bounds."""

    def taxonomy_browse(
        self, category: str | None, family: str | None
    ) -> dict:
        """Return categories, families, or decoded ordering-code facets."""

    def product_search(self, **kw: Any) -> list[dict] | dict:
        """Return matching SKUs, or ``{"error": ...}`` on invalid filters."""

    def get_sku(self, sku_code: str, include: list[str]) -> dict:
        """Return requested details for one SKU."""

    def compare_skus(
        self, sku_codes: list[str], spec_ids: list[str] | None
    ) -> dict:
        """Return a deterministic specification pivot."""

    def search_documents(self, **kw: Any) -> list[dict]:
        """Return brochure chunks with doc/page/text metadata."""

    def execute_sql(self, sql: str) -> dict:
        """Return ``{"columns": [...], "rows": [...]}`` or ``{"error": ...}``."""
