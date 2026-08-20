"""Model factory: an OpenAI-compatible path plus a native Ollama path."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from cs_agent.llm.context_guard import check_request, check_response


class EndpointConfig(BaseModel):
    provider: Literal["openai", "ollama"] = "openai"
    base_url: str
    model: str
    api_key_env: str | None = None
    temperature: float | None = None
    max_tokens: int = 4096
    timeout: float | None = 120.0
    extra_body: dict[str, Any] | None = None
    # Ollama exposes reasoning, the context window, and model residency as
    # first-class request fields; vLLM takes the equivalents through
    # `extra_body` instead.
    thinking: bool | None = None
    num_ctx: int | None = None
    # Seconds to keep the model resident after a request; -1 never unloads.
    # Unloading discards the KV cache along with the weights.
    keep_alive: float | str | None = None


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


class ContextAwareChatOllama(ChatOllama):
    """ChatOllama that reports prompts too large for its context window.

    ``_chat_params`` is the hook because it assembles the exact body sent to
    the server — converted messages *and* bound tool schemas — so the estimate
    covers what the model will actually be charged for, not just the messages
    the caller passed in.
    """

    cs_node: str = ""

    def _chat_params(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        params = super()._chat_params(messages, stop, **kwargs)
        check_request(self.cs_node, params)
        return params

    def _check(self, info: Any) -> None:
        # Rebuilt from the model's own configuration rather than stashed on
        # the instance: specialists in a stage share one cached model, so an
        # attribute set in _chat_params could belong to a sibling's request.
        check_response(
            self.cs_node,
            {"model": self.model, "options": {"num_ctx": self.num_ctx}},
            info,
        )

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[no-untyped-def]
        result = super()._generate(messages, stop, run_manager, **kwargs)
        if result.generations:
            self._check(result.generations[0].generation_info)
        return result

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[no-untyped-def]
        """Same truncation check on the streaming path.

        The specialist report and the final answer both stream, and the report
        is exactly where a silently truncated prompt does the most damage. Only
        the final chunk carries Ollama's counters, so this fires once.
        """
        for chunk in super()._stream(messages, stop, run_manager, **kwargs):
            if chunk.generation_info:
                self._check(chunk.generation_info)
            yield chunk


def _keep_alive(override: str | None, configured: float | str | None) -> float | str | None:
    """Resolve how long the server should hold the model, override winning.

    An environment variable is always a string, and Ollama reads a *string*
    keep_alive as a Go duration — so "300" is rejected outright ("missing unit
    in duration") while the number 300 means five minutes. A bare number is
    therefore converted, and anything else is passed through so "5m" and "-1s"
    still work.
    """
    if not override:
        return configured
    try:
        return float(override) if "." in override else int(override)
    except ValueError:
        return override


def _build_ollama(ep: EndpointConfig, node: str) -> ChatOllama:
    kwargs: dict[str, Any] = {
        "model": ep.model,
        "base_url": ollama_host(ep.base_url),
        # Ollama calls the output cap num_predict, and defaults the context
        # window to a fraction of what these models allow; an unset num_ctx
        # silently truncates the tool schemas out of a long prompt.
        "num_predict": ep.max_tokens,
        "num_ctx": ep.num_ctx,
        "client_kwargs": {"timeout": ep.timeout},
        "cs_node": node,
    }
    if ep.temperature is not None:
        kwargs["temperature"] = ep.temperature
    if ep.thinking is not None:
        kwargs["reasoning"] = ep.thinking
    # `keep_alive: -1` pins a model in VRAM until Ollama restarts, which is what
    # a long-lived server wants and exactly what a short-lived one does not: a
    # benchmark or a one-off script that touches a second endpoint claims another
    # model's worth of VRAM for good, and two 27B models resident at once starved
    # this box badly enough to cut decode from 38 tok/s to 12.5. CS_KEEP_ALIVE
    # overrides it so a transient caller can hand the memory back.
    keep_alive = _keep_alive(os.getenv("CS_KEEP_ALIVE"), ep.keep_alive)
    if keep_alive is not None:
        kwargs["keep_alive"] = keep_alive
    return ContextAwareChatOllama(**kwargs)


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
        return _build_ollama(ep, node)
    return _build_openai(ep)


def clear_model_cache() -> None:
    get_model.cache_clear()
