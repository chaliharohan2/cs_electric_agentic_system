"""Generate a model reply while showing it on screen as it is written.

Two kinds of caller stream, and they want different things on screen:

* **The answer** — `compose_final` and `out_of_scope` write what the user
  actually reads, so it is printed bare, under an `Answer` heading.
* **A specialist** — the tool loop and the report node write working output.
  It is printed under the agent's name, because it is a side channel and
  because specialists fan out in parallel: a token-level write straight to
  stdout would shred five agents' output together.

The report node is why this exists in its current shape. On the run it was
written against it produced 4,481 of the turn's 6,136 output tokens and 132s of
its 274s, and none of it was visible until it was finished. Watching it arrive
is the only way to see which of those tokens restate a tool result the report
did not need.

Everything else — planner, intake, the sufficiency check, analytics — passes no
label and is not streamed at all: those are short, structured, and would only
add noise.
"""

from __future__ import annotations

import os
from collections.abc import Collection
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage

from cs_agent.llm.factory import get_model
from cs_agent.observability import active_trace

# Labelled output repeats its prefix on every line, so it cannot rely on the
# terminal to wrap: a run with no newline in it is broken at this width once it
# reaches it, which also means a model emitting its whole JSON report on one
# line still shows progress. The answer is not wrapped here — it is written raw
# and the terminal wraps it, as any other text would be.
_WRAP = 100


def content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _specialists_stream() -> bool:
    """Specialist output is verbose; `CS_STREAM_AGENTS=false` silences it."""
    raw = os.getenv("CS_STREAM_AGENTS")
    return raw is None or raw.strip().lower() not in {"0", "false", "no", "off"}


def _split_line(pending: str) -> tuple[str, str]:
    """Break an over-long run at the last space, so words stay whole.

    Falls back to a hard cut when there is no space to break on — a URL or a
    long JSON string literal, both common in this output.
    """
    cut = pending.rfind(" ", _WRAP // 2, _WRAP + 1)
    if cut == -1:
        return pending[:_WRAP], pending[_WRAP:]
    return pending[:cut], pending[cut + 1 :]


class _Sink:
    """Buffer streamed text and emit it as whole lines through the trace lock."""

    def __init__(self, label: str | None, answer: bool) -> None:
        self.trace = active_trace()
        on_screen = bool(self.trace and self.trace.print_to_screen)
        self.label = label
        self.answer = answer
        self.enabled = on_screen and (
            answer or (label is not None and _specialists_stream())
        )
        self.prefix = f"  ┊ [{label}] " if label else ""
        self._pending = ""
        self.wrote = False

    def write(self, text: str) -> None:
        if not self.enabled or not text:
            return
        if not self.wrote and self.answer:
            self.trace.write("\nAnswer\n------")
        self.wrote = True
        if self.answer:
            # Raw, chunk by chunk: this is the answer the user is reading, and
            # buffering it into lines would hold tokens back for no reason.
            self.trace.write(text, end="")
            # A chat window is reading the same answer and wants it as it
            # arrives; the trace deliberately does not log these fragments.
            self.trace.notify("answer.delta", text=text)
            return
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self.trace.write(self.prefix + line)
        while len(self._pending) >= _WRAP:
            head, self._pending = _split_line(self._pending)
            self.trace.write(self.prefix + head)

    def close(self, message: BaseMessage | None) -> None:
        if not self.enabled:
            return
        if self.answer:
            if self.wrote:
                self.trace.write("")
            return
        if self._pending:
            self.trace.write(self.prefix + self._pending)
            self._pending = ""
        if self.label and (note := _cost_note(message)):
            # Watching a specialist write is only useful for finding tokens
            # worth cutting, and that judgement needs the count and the rate.
            self.trace.write(f"  ┊ [{self.label}] ⏹ {note}")


def _cost_note(message: BaseMessage | None) -> str:
    """What this generation cost, from Ollama's own counters."""
    meta = getattr(message, "response_metadata", None) or {}
    tokens = meta.get("eval_count")
    if not tokens:
        return ""
    seconds = (meta.get("eval_duration") or 0) / 1e9
    if seconds <= 0:
        return f"{tokens:,} output tokens"
    return f"{tokens:,} output tokens in {seconds:.1f}s ({tokens / seconds:.0f} tok/s)"


def _mangled_calls(message: BaseMessage, tool_names: Collection[str]) -> list[str]:
    """Tool names in ``message`` that no bound tool answers to.

    Ollama's incremental tool-call parser is less robust than its batch one. On
    a turn where qwen3.8 emitted its tool call in Qwen's XML form rather than
    the JSON Ollama expects, the streamed parse split `catalogue_map` across two
    calls — `cat\n</parameter` and `alogue_map` — while the same request
    unstreamed came back clean. A name no tool has is the signature of that
    split, and it is unambiguous: the model cannot have meant it, because it
    only ever sees the names of the tools bound to it.
    """
    return [
        name
        for call in (getattr(message, "tool_calls", None) or [])
        if (name := call.get("name") or "") not in tool_names
    ]


def generate(
    model: BaseChatModel,
    messages: list[Any],
    *,
    label: str | None = None,
    answer: bool = False,
    tool_names: Collection[str] | None = None,
) -> tuple[BaseMessage, bool]:
    """Run ``model``, streaming to screen when there is a screen to stream to.

    Returns the complete message and whether anything was printed. Chunks are
    accumulated rather than merely echoed, so a reply carrying tool calls comes
    back whole: `AIMessageChunk.__add__` merges the tool-call fragments that
    arrive across chunks. With nothing to show, this is a plain `invoke` — the
    caller's behaviour must not depend on whether anyone is watching.

    ``tool_names`` are the tools bound to ``model``. Pass them whenever the
    reply may carry a tool call: a streamed parse that produces a name none of
    them has is re-run unstreamed, because showing the work is never worth
    getting the work wrong.
    """
    sink = _Sink(label, answer)
    if not sink.enabled:
        return model.invoke(messages), False
    accumulated: BaseMessage | None = None
    try:
        for chunk in model.stream(messages):
            sink.write(content_text(chunk.content))
            accumulated = chunk if accumulated is None else accumulated + chunk
    except NotImplementedError:
        # A model wrapper without streaming still has to produce a reply.
        return model.invoke(messages), False
    if accumulated is not None and tool_names is not None:
        if mangled := _mangled_calls(accumulated, tool_names):
            if trace := active_trace():
                trace.event(
                    "llm.stream_reparse",
                    label=label,
                    mangled_tool_calls=mangled,
                    reason="streamed tool call named no bound tool; retried unstreamed",
                )
            # Half of the mangled turn is already on screen; close the sink so
            # the rest is flushed and the line ends before the retry starts.
            sink.close(accumulated)
            return model.invoke(messages), sink.wrote
    sink.close(accumulated)
    return accumulated if accumulated is not None else AIMessage(content=""), sink.wrote


def stream_answer(node: str, messages: list[Any]) -> tuple[str, bool]:
    """The user-facing answer: returns its text and whether it was shown."""
    message, shown = generate(get_model(node), messages, answer=True)
    return content_text(message.content), shown
