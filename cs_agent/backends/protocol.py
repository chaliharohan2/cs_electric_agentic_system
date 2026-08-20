"""Backend boundary for product catalogue data."""

from __future__ import annotations

from typing import Any, Protocol


class CatalogBackend(Protocol):
    def resolve_product(self, **kw: Any) -> dict:
        """Resolve codes, aliases, misspellings, and descriptions."""

    def spec_rows(self, **kw: Any) -> list[dict]:
        """Flat per-(family, spec_id) registry rows, ungrouped."""

    def list_canonical_specs(self, **kw: Any) -> dict:
        """Specification vocabulary the scope shares, detailed per group."""

    def catalogue_map(self, **kw: Any) -> dict:
        """Return taxonomy branches whose path or market segment matches."""

    def taxonomy_browse(self, **kw: Any) -> dict:
        """Return the next level of the path hierarchy."""

    def product_search(self, **kw: Any) -> dict:
        """Return matching SKUs, grouped counts, or ``{"error": ...}``."""

    def get_sku(self, sku_code: str, include: list[str], **kw: Any) -> dict:
        """Return requested details for one SKU."""

    def get_price_detail(self, sku_codes: list[str]) -> dict:
        """Return provenance-aware price observations."""

    def get_peer_group(self, sku_code: str) -> dict:
        """Return catalogue peers and comparison axes."""

    def compare_skus(
        self, sku_codes: list[str], spec_ids: list[str] | None
    ) -> dict:
        """Return a deterministic specification pivot."""

    def search_documents(self, **kw: Any) -> list[dict]:
        """Return brochure chunks with doc/page/text metadata."""

    def execute_sql(self, sql: str) -> dict:
        """Return ``{"columns": [...], "rows": [...]}`` or ``{"error": ...}``."""
