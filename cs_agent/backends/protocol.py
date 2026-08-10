"""Backend boundary for product catalogue data."""

from __future__ import annotations

from typing import Any, Protocol


class CatalogBackend(Protocol):
    def list_categories(self) -> list[dict[str, Any]]:
        """Return category dictionaries with ``id``, ``name`` and ``description``."""

    def list_facts(self, category: str) -> list[dict[str, Any]]:
        """Return canonical fact definitions for a category."""

    def product_search(
        self, category: str, filters: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Return ``products`` matching canonical-fact filters, or ``error``."""

    def get_product(self, family_id: str) -> dict[str, Any]:
        """Return one family with variants and canonical facts, or ``error``."""

    def search_documents(
        self, query: str, family_id: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Return ranked brochure chunks with document/page metadata."""

    def execute_sql(self, sql: str) -> dict[str, Any]:
        """Return ``columns`` and ``rows`` for one read-only SQL query."""
