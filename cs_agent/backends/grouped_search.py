"""Grouped product_search envelopes shared by catalogue backends."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from cs_agent.backends.path_levels import LEVEL_COLUMNS, NA, path_to_levels

GROUP_BY_VALUES = ("family", *LEVEL_COLUMNS)

GROUP_BY_SCOPE_ERROR = (
    "product_search with group_by needs family, path, or both. "
    "Grouping the whole catalogue is refused — pass the families or path "
    "prefix you are counting across, or omit group_by for a shortlist of hits. "
    "To list divisions, call taxonomy_browse with path=[]."
)


def has_search_scope(path: list[str] | None, family: Any) -> bool:
    from cs_agent.backends.matching import family_terms

    if family_terms(family):
        return True
    return bool(path)


def group_key(hit: dict[str, Any], group_by: str) -> str:
    if group_by == "family":
        return str(hit.get("family") or "")
    levels = path_to_levels(hit.get("path") or [])
    return str(levels.get(group_by) or NA)


def grouped_product_search(
    *,
    group_by: str,
    in_scope: list[dict[str, Any]],
    matched_codes: set[str],
    spec_ids_by_group: dict[str, set[str]],
    filter_spec_ids: list[str],
    limit: int,
    composite_excluded: int,
    filters_applied: list[str],
    families_not_found: list[str] | None = None,
    empty_hint: str | None = None,
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for hit in in_scope:
        buckets[group_key(hit, group_by)].append(hit)

    groups: list[dict[str, Any]] = []
    total_matched = 0
    for key in sorted(buckets):
        members = buckets[key]
        in_scope_codes: list[str] = []
        seen_scope: set[str] = set()
        for hit in members:
            code = hit["sku_code"]
            if code in seen_scope:
                continue
            seen_scope.add(code)
            in_scope_codes.append(code)
        unique_matched: list[dict[str, Any]] = []
        seen_matched: set[str] = set()
        for hit in members:
            code = hit["sku_code"]
            if code not in matched_codes or code in seen_matched:
                continue
            seen_matched.add(code)
            unique_matched.append(hit)
        matched_n = len(unique_matched)
        total_matched += matched_n
        published = spec_ids_by_group.get(key, set())
        spec_present = (
            True
            if not filter_spec_ids
            else all(spec_id in published for spec_id in filter_spec_ids)
        )
        groups.append(
            {
                group_by: key,
                "path": list(members[0].get("path") or []),
                "total_in_scope": len(in_scope_codes),
                "matched": matched_n,
                "spec_present": spec_present,
                "sample_hits": unique_matched[:limit],
            }
        )

    if empty_hint is None:
        empty_hint = (
            f"Relax {filters_applied[-1]}"
            if filters_applied
            else "Broaden the path, family, or specification filter."
        )
    result: dict[str, Any] = {
        "group_by": group_by,
        "groups": groups,
        "total_matched": total_matched,
        "composite_excluded": composite_excluded,
        "filters_applied": filters_applied,
        "widening_hint": None if total_matched else empty_hint,
    }
    if families_not_found:
        result["families_not_found"] = families_not_found
    return result
