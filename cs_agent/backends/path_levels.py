"""Compiled catalogue path depth for the SQLite artifact.

Fixed from live pre-flight on cs_electric_v2:
  max(jsonb_array_length(taxonomy->'path')) = 4
"""

from __future__ import annotations

# Exactly max observed path depth — no more, no fewer.
COMPILED_PATH_DEPTH = 4
LEVEL_COLUMNS = (
    "division",
    "product_group",
    "product_subgroup",
    "product_range",
)
NA = "N/A"

assert len(LEVEL_COLUMNS) == COMPILED_PATH_DEPTH


def path_to_levels(path: list[str] | None) -> dict[str, str]:
    """Unnest a path into fixed level columns with 'N/A' padding."""
    parts = list(path or [])
    levels: dict[str, str] = {}
    for index, column in enumerate(LEVEL_COLUMNS):
        levels[column] = parts[index] if index < len(parts) else NA
    return levels
