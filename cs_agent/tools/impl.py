"""Thin tool functions preserving the catalogue backend boundary."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from cs_agent.backends import CatalogBackend, get_backend


@lru_cache(maxsize=1)
def backend() -> CatalogBackend:
    return get_backend()


def reset_backend() -> None:
    """Clear backend selection, primarily for process-level configuration tests."""
    backend.cache_clear()


def list_categories() -> list[dict[str, Any]]:
    return backend().list_categories()


def list_facts(category: str) -> list[dict[str, Any]]:
    return backend().list_facts(category)


def product_search(category: str, filters: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [
        item.model_dump() if hasattr(item, "model_dump") else item for item in filters
    ]
    return backend().product_search(category, normalized)


def get_product(family_id: str) -> dict[str, Any]:
    return backend().get_product(family_id)


def search_documents(
    query: str, family_id: str | None = None, limit: int = 5
) -> list[dict[str, Any]]:
    return backend().search_documents(query, family_id, limit)
