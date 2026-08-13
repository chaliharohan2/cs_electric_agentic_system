"""Model factory: an OpenAI-compatible path plus a native Ollama path."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import BaseModel


class EndpointConfig(BaseModel):
    provider: Literal["openai", "ollama"] = "openai"
    base_url: str
    model: str
    api_key_env: str | None = None
    temperature: float | None = None
    max_tokens: int = 4096
    timeout: float | None = 120.0
    extra_body: dict[str, Any] | None = None
    # Ollama exposes reasoning and the context window as first-class request
    # fields; vLLM takes the equivalents through `extra_body` instead.
    thinking: bool | None = None
    num_ctx: int | None = None


class EndpointsFile(BaseModel):
    endpoints: dict[str, EndpointConfig]
    nodes: dict[str, str]


_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "endpoints.yaml"


def _load_config() -> EndpointsFile:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return EndpointsFile.model_validate(raw)


def _parse_cs_models_override() -> dict[str, str]:
    """Parse CS_MODELS=all:qwen_27b or CS_MODELS=agent:qwen_a3b,composer:qwen_27b."""
    raw = os.environ.get("CS_MODELS", "").strip()
    if not raw:
        return {}
    overrides: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        node, endpoint = part.split(":", 1)
        overrides[node.strip()] = endpoint.strip()
    return overrides


def resolve_endpoint(node: str) -> EndpointConfig:
    cfg = _load_config()
    overrides = _parse_cs_models_override()
    if "all" in overrides:
        endpoint_name = overrides["all"]
    elif node in overrides:
        endpoint_name = overrides[node]
    else:
        if node not in cfg.nodes:
            raise KeyError(f"No endpoint mapping for node '{node}' in endpoints.yaml")
        endpoint_name = cfg.nodes[node]
    if endpoint_name not in cfg.endpoints:
        raise KeyError(f"Unknown endpoint '{endpoint_name}' for node '{node}'")
    return cfg.endpoints[endpoint_name]


def _accepts_temperature(ep: EndpointConfig) -> bool:
    # Claude Sonnet 4.8+ rejects requests that carry `temperature`.
    return "api.anthropic.com" not in ep.base_url


# The Ollama client builds its own request paths from the host root, so a
# base_url copied from the API docs would otherwise become /api/chat/api/chat.
_OLLAMA_ROUTES = ("/api/chat", "/api/generate", "/v1")


def ollama_host(base_url: str) -> str:
    """Strip the API route from ``base_url``, leaving the host root."""
    host = base_url.rstrip("/")
    for route in _OLLAMA_ROUTES:
        if host.endswith(route):
            return host[: -len(route)]
    return host


def _build_ollama(ep: EndpointConfig) -> ChatOllama:
    kwargs: dict[str, Any] = {
        "model": ep.model,
        "base_url": ollama_host(ep.base_url),
        # Ollama calls the output cap num_predict, and defaults the context
        # window to a fraction of what these models allow; an unset num_ctx
        # silently truncates the tool schemas out of a long prompt.
        "num_predict": ep.max_tokens,
        "num_ctx": ep.num_ctx,
        "client_kwargs": {"timeout": ep.timeout},
    }
    if ep.temperature is not None:
        kwargs["temperature"] = ep.temperature
    if ep.thinking is not None:
        kwargs["reasoning"] = ep.thinking
    return ChatOllama(**kwargs)


def _build_openai(ep: EndpointConfig) -> ChatOpenAI:
    api_key = os.environ.get(ep.api_key_env or "") or "missing-api-key"
    kwargs: dict[str, Any] = {
        "model": ep.model,
        "base_url": ep.base_url,
        "api_key": api_key,
        "max_tokens": ep.max_tokens,
        "extra_body": ep.extra_body or {},
        "timeout": ep.timeout,
        "max_retries": 3,
    }
    if ep.temperature is not None and _accepts_temperature(ep):
        kwargs["temperature"] = ep.temperature
    return ChatOpenAI(**kwargs)


@lru_cache(maxsize=None)
def get_model(node: str) -> BaseChatModel:
    ep = resolve_endpoint(node)
    if ep.provider == "ollama":
        return _build_ollama(ep)
    return _build_openai(ep)


def clear_model_cache() -> None:
    get_model.cache_clear()
