"""Tool facade for the analytics subgraph."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage

from cs_agent.config.limits import get_limits
from cs_agent.observability import agent_scoped_config

from .build import build_analytics_graph


@lru_cache(maxsize=1)
def _graph():
    return build_analytics_graph()


def _max_queries() -> int:
    return get_limits().analytics_max_queries


def analytics_query(
    question: str,
    output_shape: str = "tabular result",
    family: str | None = None,
) -> dict[str, Any]:
    request = (
        f"Delegated question: {question}\n"
        f"Requested output shape: {output_shape or 'factual summary'}"
    )
    if family:
        request += f"\nProduct family in scope: {family}"
    state = _graph().invoke(
        {
            "messages": [HumanMessage(content=request)],
            "question": question,
            "output_shape": output_shape,
            "family": family,
            "query_count": 0,
            "query_failures": 0,
            "max_queries": _max_queries(),
        },
        config=agent_scoped_config("analytics"),
    )
    return state["answer"]
