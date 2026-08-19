"""Shared list_canonical_specs envelope used by catalogue backends."""

from __future__ import annotations

from typing import Any


def rollup_by_spec_id(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse per-(family, spec_id) rows into one row per spec_id."""
    grouped: dict[str, dict[str, Any]] = {}
    family_seen: dict[str, set[str]] = {}
    for row in rows:
        spec_id = row.get("spec_id")
        if not spec_id:
            continue
        acc = grouped.get(spec_id)
        if acc is None:
            acc = {
                "spec_id": spec_id,
                "spec_label": row.get("spec_label"),
                "unit": row.get("unit"),
                "value_kind": row.get("value_kind"),
                "is_canonical_spec": bool(row.get("is_canonical_spec")),
                "family_count": 0,
                "families": [],
                "sku_count": 0,
                "composite_count": 0,
                "observed_min": None,
                "observed_max": None,
            }
            grouped[spec_id] = acc
            family_seen[spec_id] = set()
        family = row.get("family")
        if family and family not in family_seen[spec_id]:
            family_seen[spec_id].add(family)
            acc["families"].append(family)
        if row.get("is_canonical_spec"):
            acc["is_canonical_spec"] = True
        acc["sku_count"] += int(row.get("sku_count") or 0)
        acc["composite_count"] += int(row.get("composite_count") or 0)
        low = row.get("observed_min")
        high = row.get("observed_max")
        if low is not None:
            acc["observed_min"] = (
                low if acc["observed_min"] is None else min(acc["observed_min"], low)
            )
        if high is not None:
            acc["observed_max"] = (
                high if acc["observed_max"] is None else max(acc["observed_max"], high)
            )
    for acc in grouped.values():
        acc["families"].sort()
        acc["family_count"] = len(acc["families"])
    return sorted(
        grouped.values(),
        key=lambda row: (row.get("spec_label") or "", row["spec_id"]),
    )


def specs_envelope(
    rows: list[dict[str, Any]],
    *,
    path: list[str] | None,
    family: str | list[str] | None,
) -> dict[str, Any]:
    return {
        "by_spec_id": rollup_by_spec_id(rows),
        "specs": rows,
        "scope": {"path": path or None, "family": family},
    }
