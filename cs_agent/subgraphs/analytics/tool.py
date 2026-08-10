"""Tool facade for the analytics subgraph."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .build import build_analytics_graph


@lru_cache(maxsize=1)
def _graph():
    return build_analytics_graph()


def analytics_query(
    question: str,
    scope: dict | None = None,
    output_shape: str = "tabular result",
) -> dict[str, Any]:
    state = _graph().invoke(
        {
            "question": question,
            "scope": scope,
            "output_shape": output_shape,
        }
    )
    return state["answer"]
