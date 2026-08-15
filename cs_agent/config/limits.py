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
    composer_revision_rounds: int = Field(2, ge=0)
    clarify_rounds: int = Field(2, ge=0)
    tool_failure_limit: int = Field(3, ge=1)
    max_parallel_agents: int = Field(5, ge=1, le=5)
    analytics_max_queries: int = Field(4, ge=1)
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
    "composer_revision_rounds": "CS_COMPOSER_REVISIONS",
    "clarify_rounds": "CS_CLARIFY_ROUNDS",
    "tool_failure_limit": "CS_TOOL_FAILURE_LIMIT",
    "max_parallel_agents": "CS_MAX_PARALLEL_AGENTS",
    "analytics_max_queries": "CS_ANALYTICS_MAX_QUERIES",
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
    return limits


def clear_limits_cache() -> None:
    get_limits.cache_clear()
