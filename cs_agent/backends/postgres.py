"""Future PostgreSQL catalogue adapter."""

from __future__ import annotations

from typing import Any


class PostgresBackend:
    """Schema-bound backend placeholder.

    The production database schema is intentionally not guessed. Every method
    documents its future return contract and fails explicitly.
    """

    def list_categories(self) -> list[dict[str, Any]]:
        """Return category records containing id, name, and description."""
        raise NotImplementedError("SCHEMA_PENDING")

    def list_facts(self, category: str) -> list[dict[str, Any]]:
        """Return canonical fact definitions including condition_keys."""
        raise NotImplementedError("SCHEMA_PENDING")

    def product_search(
        self, category: str, filters: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Return a mapping with a products list or an error string."""
        raise NotImplementedError("SCHEMA_PENDING")

    def get_product(self, family_id: str) -> dict[str, Any]:
        """Return a family record with variants and canonical facts."""
        raise NotImplementedError("SCHEMA_PENDING")

    def search_documents(
        self, query: str, family_id: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Return document chunks with family_id, doc, page, and text."""
        raise NotImplementedError("SCHEMA_PENDING")

    def execute_sql(self, sql: str) -> dict[str, Any]:
        """Return read-only query results as columns and rows."""
        raise NotImplementedError("SCHEMA_PENDING")
