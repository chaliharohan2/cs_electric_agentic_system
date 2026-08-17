"""Typed runtime limits loaded from YAML with environment overrides."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class Limits(BaseModel):
    global_tool_budget: int = Field(100, ge=1)
    per_agent_tool_budget: int = Field(20, ge=1)
    overview_tool_budget: int = Field(5, ge=1)
    composer_revision_rounds: int = Field(2, ge=0)
    clarify_rounds: int = Field(2, ge=0)
    tool_failure_limit: int = Field(3, ge=1)
    max_parallel_agents: int = Field(5, ge=1, le=5)
    max_stages: int = Field(3, ge=1, le=5)
    analytics_max_queries: int = Field(4, ge=1)
    # Tool-result caps. Every one of these guards a payload that was measured
    # large enough on the real catalogue to fill an 80k context window on its
    # own; see ARCHITECTURE.md "Tool result size".
    max_peer_rows: int = Field(25, ge=1)
    max_chunk_chars: int = Field(1500, ge=200)
    max_facet_rows: int = Field(60, ge=1)
    analytics_registry_chars: int = Field(24000, ge=2000)
    sqlite_path: str = "artifacts/catalog-latest.sqlite"
    checkpoint_path: str = "state/checkpoints.sqlite"
    sqlite_pragmas: dict[str, Any] = Field(
        default_factory=lambda: {
            "journal_mode": "WAL",
            "query_only": 1,
            "mmap_size": 268435456,
            "cache_size": -64000,
            "temp_store": "MEMORY",
        }
    )


_PATH = Path(__file__).with_name("limits.yaml")
_ENV_NAMES = {
    "global_tool_budget": "CS_GLOBAL_TOOL_BUDGET",
    "per_agent_tool_budget": "CS_PER_AGENT_TOOL_BUDGET",
    "overview_tool_budget": "CS_OVERVIEW_TOOL_BUDGET",
    "composer_revision_rounds": "CS_COMPOSER_REVISIONS",
    "clarify_rounds": "CS_CLARIFY_ROUNDS",
    "tool_failure_limit": "CS_TOOL_FAILURE_LIMIT",
    "max_parallel_agents": "CS_MAX_PARALLEL_AGENTS",
    "max_stages": "CS_MAX_STAGES",
    "analytics_max_queries": "CS_ANALYTICS_MAX_QUERIES",
    "max_peer_rows": "CS_MAX_PEER_ROWS",
    "max_chunk_chars": "CS_MAX_CHUNK_CHARS",
    "max_facet_rows": "CS_MAX_FACET_ROWS",
    "analytics_registry_chars": "CS_ANALYTICS_REGISTRY_CHARS",
}
_ENV_STRINGS = {
    "sqlite_path": "CS_SQLITE_PATH",
    "checkpoint_path": "CS_CHECKPOINT_PATH",
}


@lru_cache(maxsize=1)
def get_limits() -> Limits:
    with _PATH.open(encoding="utf-8") as handle:
        values = yaml.safe_load(handle) or {}
    for field_name, env_name in _ENV_NAMES.items():
        if raw := os.getenv(env_name):
            values[field_name] = int(raw)
    for field_name, env_name in _ENV_STRINGS.items():
        if raw := os.getenv(env_name):
            values[field_name] = raw
    limits = Limits.model_validate(values)
    if limits.per_agent_tool_budget > limits.global_tool_budget:
        raise ValueError("per_agent_tool_budget cannot exceed global_tool_budget")
    if limits.overview_tool_budget > limits.per_agent_tool_budget:
        raise ValueError("overview_tool_budget cannot exceed per_agent_tool_budget")
    return limits


def clear_limits_cache() -> None:
    get_limits.cache_clear()
