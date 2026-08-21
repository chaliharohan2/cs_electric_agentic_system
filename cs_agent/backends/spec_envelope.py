"""Grouped, intersecting list_canonical_specs payloads.

A specialist asks about several families at once in order to *compare* them, so
what it needs back is the vocabulary those families share, stated per family.
Returning the union instead answered a question nobody asked: for two ACB
ranges it came to 110 spec ids of which only 18 are held by both, and the 92
left over are mostly per-family naming debris — `3p_n` in one range and `3pn`
in the other, `1000_1600a`, `415v_ac`, `a2`…`a5`. Those cannot be compared
across the scope, and they made the payload 31,354 characters where the shared
vocabulary is 8,496.

So the intersection leads, and every excluded id is still named — cheaply, as a
name against the groups that hold it — because silence would read as "the
catalogue does not publish this" when the truth is "only one of these families
does, ask for it alone".
"""

from __future__ import annotations

from typing import Any


# Fields that describe the specification itself and are therefore the same
# whichever group publishes it; everything else is stated per group.
#
# `is_canonical_spec` is deliberately not among them, and is published on no
# payload at all. It splits the catalogue almost evenly — 123,800 rows true
# against 139,828 false — so it is a real signal, and it was read by nothing:
# it reached neither of two captured specialist reports, no prompt mentions it,
# and no consumer outside the catalogue itself touched it. It survives in the
# built artifact, where the `canonical_only` filter and the analytics
# vocabulary ordering still use it; it just stopped being sent to a model.
SHARED_FIELDS = ("spec_label", "unit", "value_kind")
# Fields whose value belongs to one group and must not be merged across them:
# WiNmaster 3 reaching 4000 A where WiNmaster 2 stops at 2500 A is exactly the
# difference a comparison is about.
PER_GROUP_FIELDS = ("sku_count", "composite_count", "observed_min", "observed_max")
MAX_NOT_SHARED = 60


def group_specs(
    rows: list[dict[str, Any]],
    *,
    groups: list[str],
    group_by: str,
    path: list[str] | None,
    family: str | list[str] | None,
) -> dict[str, Any]:
    """One row per spec id the whole scope shares, detailed per group.

    ``rows`` are the flat per-(group, spec_id) records; ``groups`` is every
    group in scope, which has to be passed in rather than inferred from the
    rows — a group that publishes no matching spec at all still has to count
    against the intersection, or a spec held by one family out of three would
    be reported as shared by all of them.
    """
    by_spec: dict[str, dict[str, Any]] = {}
    holders: dict[str, list[str]] = {}
    for row in rows:
        spec_id = row.get("spec_id")
        group = row.get(group_by) or row.get("family")
        if not spec_id or group is None:
            continue
        group = str(group)
        entry = by_spec.setdefault(spec_id, {"spec_id": spec_id, "by_group": {}})
        for field in SHARED_FIELDS:
            if row.get(field) is not None and field not in entry:
                entry[field] = row[field]
        detail = {
            field: row[field]
            for field in PER_GROUP_FIELDS
            if row.get(field) is not None
        }
        entry["by_group"][group] = detail
        holders.setdefault(spec_id, []).append(group)

    in_scope = [str(g) for g in groups]
    wanted = set(in_scope)
    shared, partial = [], {}
    for spec_id, entry in by_spec.items():
        held = wanted & set(holders.get(spec_id) or [])
        if held == wanted and wanted:
            shared.append(entry)
        else:
            partial[spec_id] = sorted(held)
    shared.sort(key=lambda e: (e.get("spec_label") or "", e["spec_id"]))

    payload: dict[str, Any] = {
        "scope": {
            "path": path or None,
            "family": family,
            "group_by": group_by,
            "groups": in_scope,
        },
        "specs": shared,
    }
    if partial:
        payload["not_shared"] = {
            "note": (
                f"{len(partial)} more specification ids exist in some but not all "
                f"of the {len(in_scope)} groups in scope, so they cannot be "
                "compared across it. They are named here rather than returned: "
                "call again with the single group to get one of them in full."
            ),
            "spec_ids": dict(sorted(partial.items())[:MAX_NOT_SHARED]),
        }
        if len(partial) > MAX_NOT_SHARED:
            payload["not_shared"]["truncated_after"] = MAX_NOT_SHARED
    return payload


# Keys a nested spec row inherits from the hit it hangs under, or that name a
# database row rather than anything about the product.
NESTED_REDUNDANT = ("sku_code", "product_id")


def compact_fact(row: dict[str, Any], *, drop: tuple[str, ...] = ()) -> dict[str, Any]:
    """A spec row with nothing in it that says nothing.

    Two thirds of a `return_specs` block is structure rather than content. On a
    measured comparison call — 10 hits, 38 specs requested, 112 rows attached —
    the block came to 37,696 of the payload's 44,190 characters, and of that:

        keys whose value was null      10,022   26.6%
        sku_code + product_id           5,602   14.9%

    A null says "not published", which is exactly what an absent key says, and
    the tool description already tells the model that a missing specification
    means not published rather than zero. `sku_code` repeats the parent hit's
    own field on every one of its rows, and `product_id` is an internal row id
    the model has no use for and must not quote.

    What stays is everything that carries meaning, including `source_of_truth`,
    which takes three distinct values here, one of which — `pricelist_table` —
    is what a price citation is built from.

    `spec_label` used to be defended here too, on the grounds that it differs
    from `spec_id` irrecoverably on 41% of the catalogue's 1,112 label pairs
    (`1_no_1_nc` is published as `1 NO + 1 NC`). That is still true, and it is
    still why `list_canonical_specs` publishes labels. It stopped being an
    argument for repeating one on every attached spec row: a `return_specs`
    block asks for specifications the caller has already named by id, and on one
    measured call the seven ids it named carried seven labels across 274 rows.
    """
    return {
        key: value
        for key, value in row.items()
        if value is not None and key not in drop
    }
