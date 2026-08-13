"""Tool facade for the analytics subgraph."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage

from .build import build_analytics_graph

DEFAULT_MAX_QUERIES = 4


@lru_cache(maxsize=1)
def _graph():
    return build_analytics_graph()


def _max_queries() -> int:
    raw = os.getenv("CS_ANALYTICS_MAX_QUERIES", str(DEFAULT_MAX_QUERIES))
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_QUERIES
    return value if value > 0 else DEFAULT_MAX_QUERIES


def analytics_query(
    question: str,
    output_shape: str = "tabular result",
) -> dict[str, Any]:
    request = (
        f"Delegated question: {question}\n"
        f"Requested output shape: {output_shape or 'factual summary'}"
    )
    state = _graph().invoke(
        {
            "messages": [HumanMessage(content=request)],
            "question": question,
            "output_shape": output_shape,
            "query_count": 0,
            "query_failures": 0,
            "max_queries": _max_queries(),
        }
    )
    return state["answer"]
