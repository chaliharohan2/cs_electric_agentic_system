"""Plain-English progress lines, built from the trace the agent already emits.

A turn takes around two minutes, so a chat window that shows nothing until the
answer arrives looks broken. `tool.start` already carries the tool name and its
parsed arguments, which is enough to say what is happening in the customer's
own vocabulary — "Searching the catalogue for MCB" rather than
`catalogue_map({"path_text": "MCB"})`.

This lives in the backend rather than the frontend because knowing that
`path_text` is the interesting argument on `catalogue_map` and `text` on
`product_search` is knowledge about the tools, and it should survive replacing
the UI.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

_CLIP = 60


def _clip(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= _CLIP else text[: _CLIP - 1].rstrip() + "…"


def _codes(value: Any) -> str | None:
    """Ordering codes read better named than counted, up to a point."""
    items = [str(v) for v in value if v]
    if not items:
        return None
    if len(items) <= 2:
        return " and ".join(items)
    return f"{items[0]} and {len(items) - 1} others"


def _path(value: Any) -> str | None:
    parts = [str(p) for p in value if p]
    return " > ".join(parts) if parts else None


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


# How an argument reads inside a sentence. Anything absent is rendered as text.
_RENDER: dict[str, Callable[[Any], str | None]] = {
    "path": _path,
    "scope": _path,
    "sku_codes": _codes,
    "filters": lambda v: _plural(len(v), "specification") if v else None,
    "facets": lambda v: ", ".join(str(x) for x in v.values()) if v else None,
}

# First argument present wins, so the most specific phrasing is tried first.
_PHRASES: dict[str, tuple[tuple[str, str], ...]] = {
    "catalogue_map": (
        ("path_text", "Searching the catalogue for {}"),
        ("market_segment", "Finding what C&S makes for {}"),
    ),
    "taxonomy_browse": (("path", "Opening {}"),),
    "product_search": (
        ("text", "Searching products for {}"),
        ("facets", "Searching products for {}"),
        ("filters", "Filtering products on {}"),
        ("family", "Looking through {}"),
        ("path", "Looking through {}"),
        ("market_segment", "Looking through products for {}"),
    ),
    "resolve_product": (("query", "Looking up {}"),),
    "get_sku": (("sku_code", "Reading the catalogue entry for {}"),),
    "compare_skus": (("sku_codes", "Comparing {}"),),
    "get_peer_group": (("sku_code", "Finding alternatives to {}"),),
    "get_price_detail": (("sku_codes", "Checking the price of {}"),),
    "list_canonical_specs": (
        ("family", "Listing the specifications published for {}"),
        ("spec_id_contains", "Looking for specifications about {}"),
    ),
    "search_documents": (
        ("family", "Reading what the catalogue says about {}"),
        ("sku_code", "Reading what the catalogue says about {}"),
        ("query", "Reading the catalogue on {}"),
    ),
    "analytics_query": (
        ("family", "Analysing {} across the catalogue"),
        ("question", "Working out {}"),
    ),
}

# Used when no argument in the table is set — an empty `path` on
# `taxonomy_browse` is the common one, and it means the top of the tree.
_FALLBACK: dict[str, str] = {
    "catalogue_map": "Searching the catalogue",
    "taxonomy_browse": "Opening the top of the catalogue",
    "product_search": "Searching the product catalogue",
    "resolve_product": "Looking up a product code",
    "get_sku": "Reading a catalogue entry",
    "compare_skus": "Comparing products",
    "get_peer_group": "Finding alternatives",
    "get_price_detail": "Checking prices",
    "list_canonical_specs": "Listing published specifications",
    "search_documents": "Reading the catalogue",
    "analytics_query": "Running the numbers",
}


def tool_phrase(tool: str, inputs: Mapping[str, Any] | None) -> str:
    """What a `tool.start` event should say to someone watching.

    Falls back to the tool's own sentence when the interesting argument is
    absent, and to the bare name for a tool this table has never heard of — a
    new tool should read plainly rather than break the window.
    """
    for argument, template in _PHRASES.get(tool, ()):
        value = (inputs or {}).get(argument)
        if value in (None, "", [], {}):
            continue
        render = _RENDER.get(argument)
        shown = render(value) if render else _clip(str(value))
        if shown:
            return template.format(shown)
    return _FALLBACK.get(tool, f"Running {tool.replace('_', ' ')}")


# The specialists are private to the graph; these are how their work reads from
# outside it. Keys are the agent names in `tools/registry.AGENT_TOOL_NAMES`.
# Each is a display name and what that specialist is there to do — the name is
# carried because "which specialist is running" is the interesting half when
# five of them exist and a turn uses two or three.
_AGENTS: dict[str, tuple[str, str]] = {
    "discovery": ("Discovery", "finding what C&S sells here"),
    "spec_selection": ("Spec selection", "matching the specifications"),
    "solution_advisory": ("Solution advisory", "working out a recommendation"),
    "comparison": ("Comparison", "comparing the options"),
    "compliance": ("Compliance", "checking standards and ratings"),
    "analytics": ("Analytics", "running the numbers"),
}

# Graph nodes worth showing. Everything else is bookkeeping and stays hidden.
_NODES: dict[str, str] = {
    "intake": "Reading your question",
    "planner": "Planning the work",
    "gate": "Checking the findings",
    "composer": "Checking the evidence is enough",
    "compose_final": "Writing the answer",
    "out_of_scope": "Writing the answer",
}


def agent_phrase(agent: str | None) -> str | None:
    """A specialist starting work, named."""
    entry = _AGENTS.get(agent or "")
    return f"{entry[0]} specialist — {entry[1]}" if entry else None


def report_phrase(agent: str | None) -> str | None:
    """A specialist writing up what it found.

    Worth its own line: on a detailed brief the report is the largest single
    generation in the turn, so without it the window looks stalled for the
    longest stretch of the run.
    """
    entry = _AGENTS.get(agent or "")
    if not entry:
        return None
    return f"{entry[0]} specialist is writing its final evidence report"


def node_phrase(node: str | None) -> str | None:
    return _NODES.get(node or "")
