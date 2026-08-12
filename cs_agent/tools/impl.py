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


def list_canonical_specs(category: str | None = None) -> list[dict[str, Any]]:
    return backend().list_canonical_specs(category)


def taxonomy_browse(
    category: str | None = None, family: str | None = None
) -> dict[str, Any]:
    return backend().taxonomy_browse(category, family)


def product_search(
    category: str | None = None,
    family: str | None = None,
    facets: dict[str, str] | None = None,
    filters: list[Any] | None = None,
    text: str | None = None,
    return_specs: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]] | dict[str, Any]:
    normalized = []
    for item in filters or []:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        normalized.append(data)
    return backend().product_search(
        category=category,
        family=family,
        facets=facets,
        filters=normalized,
        text=text,
        return_specs=return_specs or [],
        limit=limit,
    )


def get_sku(
    sku_code: str,
    include: list[str] | None = None,
) -> dict[str, Any]:
    return backend().get_sku(sku_code, include or ["facts", "decoded"])


def compare_skus(
    sku_codes: list[str],
    spec_ids: list[str] | None = None,
) -> dict[str, Any]:
    return backend().compare_skus(sku_codes, spec_ids)


def search_documents(
    query: str,
    category: str | None = None,
    family: str | None = None,
    sku_code: str | None = None,
    k: int = 6,
) -> list[dict[str, Any]]:
    return backend().search_documents(
        query=query,
        category=category,
        family=family,
        sku_code=sku_code,
        k=k,
    )
