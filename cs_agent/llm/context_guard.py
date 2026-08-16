"""Report when a prompt will not fit in an Ollama context window.

Ollama does not fail a request whose prompt exceeds ``num_ctx``. It drops the
overflow and answers anyway, and what it drops is the *head* of the prompt —
the system prompt, the brief, and the tool schemas. The model then behaves as
if it had never been told the rules: it invents tool names, ignores the report
contract, and the run looks like a model-quality problem rather than a prompt
that was silently cut in half.

Two signals are emitted, because neither alone is sufficient:

* **Before the call** — an estimate from the assembled request body. Always
  available, but approximate: it counts characters, not tokens.
* **After the call** — Ollama's own ``prompt_eval_count``. Exact, but reported
  only when the server chooses to, and prefix-cache hits can make it read low,
  so a *small* count proves nothing while a count pinned at ``num_ctx`` is hard
  evidence the window was filled.
"""

from __future__ import annotations

import json
import os
from typing import Any

from cs_agent.observability import active_trace

# Characters per token. JSON with punctuation, digits and ordering codes
# tokenizes worse than prose, so this sits below the usual English figure of 4:
# for a warning, over-estimating the prompt is the safe direction.
DEFAULT_CHARS_PER_TOKEN = 3.5

# Fraction of the usable window that counts as "close enough to warn about".
PRESSURE_RATIO = 0.85


def _chars_per_token() -> float:
    raw = os.getenv("CS_CHARS_PER_TOKEN")
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_CHARS_PER_TOKEN


def _chars(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    return len(json.dumps(value, default=str))


def estimate(params: dict[str, Any]) -> dict[str, int]:
    """Size the parts of an Ollama chat request, in estimated tokens."""
    ratio = _chars_per_token()
    message_chars = _chars(params.get("messages"))
    tool_chars = _chars(params.get("tools"))
    return {
        "message_chars": message_chars,
        "tool_schema_chars": tool_chars,
        "estimated_message_tokens": int(message_chars / ratio),
        "estimated_tool_schema_tokens": int(tool_chars / ratio),
        "estimated_prompt_tokens": int((message_chars + tool_chars) / ratio),
    }


def check_request(node: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Warn if the assembled request cannot fit its context window.

    Returns the report it emitted, or None when the prompt is comfortable.
    """
    options = params.get("options") or {}
    num_ctx = options.get("num_ctx")
    if not num_ctx:
        return None
    num_predict = options.get("num_predict") or 0
    # The window holds the prompt and the answer, so the reply Ollama has been
    # told to reserve is not space the prompt can use.
    usable = max(1, int(num_ctx) - int(num_predict))
    sizes = estimate(params)
    estimated = sizes["estimated_prompt_tokens"]
    if estimated < usable * PRESSURE_RATIO:
        return None
    report = {
        "node": node,
        "model": params.get("model"),
        "num_ctx": int(num_ctx),
        "num_predict": int(num_predict),
        "usable_prompt_tokens": usable,
        "message_count": len(params.get("messages") or []),
        "tool_count": len(params.get("tools") or []),
        **sizes,
    }
    trace = active_trace()
    if estimated >= usable:
        report["overflow_tokens"] = estimated - usable
        report["note"] = (
            "Estimated prompt exceeds the usable window. Ollama truncates the "
            "head of the prompt silently, which drops the system prompt and "
            "tool schemas first."
        )
        if trace:
            trace.event("llm.context_overflow", **report)
    else:
        report["note"] = (
            f"Estimated prompt is within {int(PRESSURE_RATIO * 100)}% of the "
            "usable window; a few more tool results will overflow it."
        )
        if trace:
            trace.event("llm.context_pressure", **report)
    return report


def check_response(node: str, params: dict[str, Any], info: Any) -> None:
    """Confirm truncation from Ollama's own prompt token count, when given."""
    if not isinstance(info, dict):
        return
    evaluated = info.get("prompt_eval_count")
    num_ctx = (params.get("options") or {}).get("num_ctx")
    if not evaluated or not num_ctx:
        return
    # Ollama cannot evaluate more prompt tokens than the window holds, so a
    # count sitting at the cap means the window was filled and the rest of the
    # prompt was discarded. A low count proves nothing: prefix-cache hits are
    # not re-evaluated.
    if int(evaluated) < int(num_ctx) * 0.98:
        return
    if trace := active_trace():
        trace.event(
            "llm.prompt_truncated",
            node=node,
            model=params.get("model"),
            num_ctx=int(num_ctx),
            prompt_eval_count=int(evaluated),
            note=(
                "Ollama evaluated a full context window of prompt tokens, so "
                "the prompt was cut to fit. Reduce tool-result size or raise "
                "num_ctx for this endpoint."
            ),
        )
