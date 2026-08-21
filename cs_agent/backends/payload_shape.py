"""Shaping applied to tool payloads at the backend boundary.

Measured on the two captured specialist report calls: five `get_sku` payloads
were 63.5% of one report's input, and three `product_search` payloads were 91%
of the other's — an input that sat at 58,822 tokens against a 60,000-token
usable window, roughly one tool call from the silent head-truncation that turned
a measured run from 86s into 365s.

Everything here removes bytes without removing facts. Two moves do the work:

`flatten_decoded` drops the half of each decoded axis that the ordering code
already spells. An axis arrives as ``{"code": "MDO", "meaning": "Manual Draw Out
Type"}`` on a hit whose `sku_code` is ``WX306L3P1MDOA(S)`` — the code is a
literal substring of the identifier printed on the same line, so only the
meaning is telling the reader something.

`hoist_scope` states once what is true of every row. A `product_search` over one
family returned the same `url` on all 40 hits (the catalogue publishes 42 URLs
for 11,250 SKUs) and the same four-element `path` on all 40; together with
`family` that was 11,200 characters spent repeating three values 40 times. The
values still reach the model, in a `scope` object beside the rows.

Uniformity is checked per call rather than assumed, so a grouped search — where
`family` genuinely differs between rows — keeps its per-row fields.
"""

from __future__ import annotations

import json
from typing import Any

# Meanings that name the absence of a decode. Emitting the axis anyway costs the
# bytes of saying "we could not read this segment", which is what leaving the
# axis out says for free.
_EMPTY_MEANINGS = ("", "unknown")

# Fields a `product_search` hit inherits from the search itself rather than owns.
SEARCH_SCOPE_FIELDS = ("url", "path", "family")
# A peer group sits inside one family by construction.
PEER_SCOPE_FIELDS = ("family",)


def flatten_decoded(decoded: Any) -> dict[str, Any]:
    """One entry per decoded axis, holding its meaning rather than a pair.

    Nested meanings survive as they are: `breaking` decodes to
    ``{"ka": 80, "volts": 415}``, which is two facts and not a restatement. The
    exception is a single-key mapping whose key repeats the axis name — `poles`
    decoding to ``{"poles": 3}`` — where the wrapper says nothing.
    """
    if not isinstance(decoded, dict):
        return {}
    flat: dict[str, Any] = {}
    for axis, spec in decoded.items():
        meaning = spec.get("meaning") if isinstance(spec, dict) else spec
        if isinstance(meaning, dict) and len(meaning) == 1 and axis in meaning:
            meaning = meaning[axis]
        if meaning is None:
            continue
        if isinstance(meaning, str) and meaning.strip().lower() in _EMPTY_MEANINGS:
            continue
        flat[axis] = meaning
    return flat


def hoist_scope(
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> dict[str, Any]:
    """Move every field uniform across `rows` into the payload's `scope`.

    A field that varies stays where it is, so this is safe to call on a grouped
    result whose rows span families. A field uniform at `None` is dropped
    outright rather than hoisted: an absent key already says "not published",
    which is what the tool descriptions tell the model a missing value means.
    """
    rows = [row for row in rows if isinstance(row, dict)]
    if not rows:
        return payload
    scope: dict[str, Any] = dict(payload.get("scope") or {})
    for field in fields:
        seen = {
            json.dumps(row.get(field), sort_keys=True, default=str) for row in rows
        }
        if len(seen) != 1:
            continue
        value = rows[0].get(field)
        for row in rows:
            row.pop(field, None)
        if value not in (None, "", [], {}):
            scope[field] = value
    if scope:
        payload["scope"] = scope
    return payload


def merge_scope(payload: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """A row read back with whatever its payload hoisted out of it.

    For the code that consumes payloads rather than the model that reads them:
    the derived-report builders index hits by family, path and URL, and after a
    hoist those live one level up. The row's own values win, so this is correct
    whether or not the hoist actually fired.
    """
    scope = payload.get("scope")
    if not isinstance(scope, dict) or not isinstance(row, dict):
        return row
    return {**scope, **row}
