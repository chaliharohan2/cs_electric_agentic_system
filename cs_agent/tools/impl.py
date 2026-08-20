"""Thin tool functions preserving the catalogue backend boundary."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from cs_agent.backends import CatalogBackend, get_backend
from cs_agent.backends.matching import family_terms, normalize, squash, unmatched_family_terms


@lru_cache(maxsize=1)
def backend() -> CatalogBackend:
    return get_backend()


def reset_backend() -> None:
    """Clear backend selection, primarily for process-level configuration tests."""
    backend.cache_clear()
    _known_families.cache_clear()


def resolve_product(
    query: str, family_hint: str | None = None, limit: int = 8
) -> dict[str, Any]:
    return backend().resolve_product(
        query=query, family_hint=family_hint, limit=limit
    )


@lru_cache(maxsize=1)
def _known_families() -> tuple[str, ...]:
    """Every family name the catalogue actually uses.

    One query per process, kept as names only. It exists so an empty result can
    tell the caller *why* it is empty; the alternative is what was measured — a
    specialist re-issuing the same guessed family name until its budget ran out.
    """
    names = {
        row.get("family") for row in backend().spec_rows() if row.get("family")
    }
    return tuple(sorted(names))


def _closest_families(wanted: str, limit: int = 6) -> list[str]:
    """Families worth trying instead of one that matched nothing."""
    needle = squash(wanted)
    words = {word for word in normalize(wanted).split() if len(word) > 2}
    scored: list[tuple[int, str]] = []
    for name in _known_families():
        key = squash(name)
        overlap = len(words & set(normalize(name).split()))
        if needle and (needle in key or key in needle):
            scored.append((100, name))
        elif overlap:
            scored.append((overlap, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored[:limit]]


def _unmatched_families(family: str | list[str] | None) -> list[str]:
    if not family_terms(family):
        return []
    return unmatched_family_terms(family, _known_families())


def _closest_for_terms(wanted: list[str], limit: int = 6) -> list[str]:
    seen: set[str] = set()
    closest: list[str] = []
    for term in wanted:
        for name in _closest_families(term, limit=limit):
            if name in seen:
                continue
            seen.add(name)
            closest.append(name)
            if len(closest) >= limit:
                return closest
    return closest


def _annotate_family_misses(
    result: dict[str, Any], family: str | list[str] | None
) -> dict[str, Any]:
    missed = list(result.get("families_not_found") or []) or _unmatched_families(family)
    if not missed:
        return result
    result = dict(result)
    result["families_not_found"] = missed
    if isinstance(family, str):
        result["family_not_found"] = family
    result["closest_families"] = _closest_for_terms(missed)
    has_payload = bool(
        result.get("specs") or result.get("hits") or result.get("groups")
    )
    if not has_payload:
        named = ", ".join(repr(term) for term in missed)
        result["hint"] = (
            f"No family is named {named}. Try one of closest_families, or "
            "call taxonomy_browse to see what C&S actually publishes. Calling "
            "this again with the same family will return the same nothing."
        )
    return result


def list_canonical_specs(
    family: str | list[str] | None = None,
    spec_id_contains: str | None = None,
    canonical_only: bool = False,
    path: list[str] | None = None,
    group_by: str | None = None,
) -> dict[str, Any]:
    result = backend().list_canonical_specs(
        family=family,
        spec_id_contains=spec_id_contains,
        canonical_only=canonical_only,
        path=path,
        group_by=group_by,
    )
    return _annotate_family_misses(result, family)


def catalogue_map(
    path_text: str | None = None,
    market_segment: str | None = None,
    include_uncategorised: bool = True,
    limit: int = 40,
) -> dict[str, Any]:
    return backend().catalogue_map(
        path_text=path_text,
        market_segment=market_segment,
        include_uncategorised=include_uncategorised,
        limit=limit,
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
    family: str | list[str] | None = None,
    facets: dict[str, str] | None = None,
    filters: list[Any] | None = None,
    market_segment: str | None = None,
    price_status: list[str] | str | None = None,
    has_chunk_type: list[str] | None = None,
    text: str | None = None,
    return_specs: list[str] | None = None,
    limit: int = 20,
    group_by: str | None = None,
) -> dict[str, Any]:
    normalized = []
    for item in filters or []:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        normalized.append(data)
    if isinstance(price_status, str):
        price_status = [price_status]
    result = backend().product_search(
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
        group_by=group_by,
    )
    if isinstance(result, dict) and family_terms(family):
        return _annotate_family_misses(result, family)
    return result


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
