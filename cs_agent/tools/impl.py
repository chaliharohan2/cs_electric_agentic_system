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


def resolve_product(
    query: str, family_hint: str | None = None, limit: int = 8
) -> dict[str, Any]:
    return backend().resolve_product(
        query=query, family_hint=family_hint, limit=limit
    )


def list_canonical_specs(
    family: str | None = None,
    spec_id_contains: str | None = None,
    canonical_only: bool = False,
) -> list[dict[str, Any]]:
    return backend().list_canonical_specs(
        family=family,
        spec_id_contains=spec_id_contains,
        canonical_only=canonical_only,
    )


def taxonomy_browse(
    path: list[str] | None = None,
    market_segment: str | None = None,
    include_facets: bool = False,
) -> dict[str, Any]:
    return backend().taxonomy_browse(
        path=path,
        market_segment=market_segment,
        include_facets=include_facets,
    )


def product_search(
    path: list[str] | None = None,
    family: str | None = None,
    facets: dict[str, str] | None = None,
    filters: list[Any] | None = None,
    market_segment: str | None = None,
    price_status: list[str] | None = None,
    has_chunk_type: list[str] | None = None,
    text: str | None = None,
    return_specs: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]] | dict[str, Any]:
    normalized = []
    for item in filters or []:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        normalized.append(data)
    return backend().product_search(
        path=path,
        family=family,
        facets=facets,
        filters=normalized,
        market_segment=market_segment,
        price_status=price_status,
        has_chunk_type=has_chunk_type,
        text=text,
        return_specs=return_specs or [],
        limit=limit,
    )


def get_sku(
    sku_code: str,
    include: list[str] | None = None,
    chunk_types: list[str] | None = None,
) -> dict[str, Any]:
    return backend().get_sku(
        sku_code,
        include or ["facts", "decoded", "sources"],
        chunk_types=chunk_types,
    )


def get_price_detail(sku_codes: list[str]) -> dict[str, Any]:
    return backend().get_price_detail(sku_codes)


def get_peer_group(sku_code: str) -> dict[str, Any]:
    return backend().get_peer_group(sku_code)


def compare_skus(
    sku_codes: list[str],
    spec_ids: list[str] | None = None,
) -> dict[str, Any]:
    return backend().compare_skus(sku_codes, spec_ids)


def search_documents(
    query: str,
    path: list[str] | None = None,
    family: str | None = None,
    sku_code: str | None = None,
    chunk_types: list[str] | None = None,
    k: int = 6,
) -> list[dict[str, Any]]:
    return backend().search_documents(
        query=query,
        path=path,
        family=family,
        sku_code=sku_code,
        chunk_types=chunk_types,
        k=k,
    )
