"""Configuration-driven construction of OpenAI-compatible chat models."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from langchain_openai import ChatOpenAI

CONFIG_PATH = Path(__file__).parents[1] / "config" / "endpoints.yaml"


@lru_cache(maxsize=1)
def _config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _model_overrides() -> dict[str, str]:
    value = os.getenv("CS_MODELS", "")
    overrides: dict[str, str] = {}
    for item in filter(None, (part.strip() for part in value.split(","))):
        if ":" not in item:
            raise ValueError(f"Invalid CS_MODELS entry {item!r}; expected node:model")
        node, model = item.split(":", 1)
        overrides[node.strip()] = model.strip()
    return overrides


def get_model(node: str) -> ChatOpenAI:
    """Return the configured model for a graph node.

    ``CS_MODELS`` accepts either ``all:qwen_27b`` or comma-separated
    node-specific mappings such as ``agent:qwen_a3b,composer:qwen_27b``.
    """

    config = _config()
    overrides = _model_overrides()
    model_key = overrides.get(node, overrides.get("all", config["nodes"].get(node)))
    if not model_key:
        model_key = config["defaults"]["model"]
    if model_key not in config["models"]:
        raise ValueError(f"Unknown model alias {model_key!r}")

    model_config = config["models"][model_key]
    endpoint_key = model_config.get("endpoint", config["defaults"]["endpoint"])
    endpoint = config["endpoints"][endpoint_key]
    api_key = os.getenv(endpoint.get("api_key_env", "CS_API_KEY")) or os.getenv(
        "OPENAI_API_KEY"
    )
    base_url = os.getenv(endpoint.get("base_url_env", "CS_BASE_URL"))
    if not api_key:
        # ChatOpenAI validates eagerly. A harmless placeholder permits graph
        # construction and offline backend tests without making a request.
        api_key = "not-configured"

    kwargs: dict[str, Any] = {
        "model": model_config["model_name"],
        "api_key": api_key,
        "temperature": model_config.get(
            "temperature", config["defaults"].get("temperature", 0)
        ),
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)
