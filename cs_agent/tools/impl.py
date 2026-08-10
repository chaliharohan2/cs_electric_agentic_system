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


def list_canonical_facts(category_path: str | None = None) -> list[dict[str, Any]]:
    return backend().list_canonical_facts(category_path)


def taxonomy_browse(node_id: str | None = None, depth: int = 1) -> dict[str, Any]:
    return backend().taxonomy_browse(node_id, depth)


def product_search(
    category_path: str,
    filters: list[Any] | None = None,
    text: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]] | dict[str, Any]:
    normalized = []
    for item in filters or []:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        normalized.append(data)
    return backend().product_search(
        category_path=category_path,
        filters=normalized,
        text=text,
        limit=limit,
    )


def get_product(
    family_id: str,
    fact_groups: list[str],
    include_variants: bool = False,
) -> dict[str, Any]:
    return backend().get_product(family_id, fact_groups, include_variants)


def search_documents(
    query: str,
    category_path: str | None = None,
    family_id: str | None = None,
    k: int = 6,
) -> list[dict[str, Any]]:
    return backend().search_documents(
        query=query,
        category_path=category_path,
        family_id=family_id,
        k=k,
    )
