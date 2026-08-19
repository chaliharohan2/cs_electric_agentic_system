"""A chat window over the agent, for showing it to people.

The agent is not modified to run here. A turn is `run_question`, exactly as the
CLI calls it, on a worker thread; this module watches the trace that turn was
already writing and renders it. Everything the CLI prints still prints, and the
JSONL trace is still written, because the listener is handed each record after
the file and the screen have had it.

Two things a chat window needs that a terminal does not:

* **Progress.** A turn takes around two minutes. `tool.start` and `node.start`
  carry what is happening and who is doing it, and `ui/phrases.py` turns those
  into sentences a customer would recognise.
* **Somewhere to put a clarifying question.** The CLI answers the clarify
  interrupt with `input()`. Here the question is shown in the chat and answered
  by the next thing the user types, which `resume_question` picks up off the
  checkpoint.

One turn runs at a time (`concurrency_limit=1`), because the trace the model
factory reports through is a module-level handle with one process, one turn.
"""

from __future__ import annotations

import os
import queue
import threading
import uuid
from typing import Any

import gradio as gr
from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler

from cs_agent.observability import TraceLogger, set_active_trace
from cs_agent.run import (
    TurnCancelled,
    interrupt_questions,
    resume_question,
    run_question,
)
from cs_agent.ui.phrases import (
    agent_phrase,
    node_phrase,
    report_phrase,
    tool_phrase,
)

TITLE = "C&S Electric — product support"
DESCRIPTION = (
    "Ask about C&S products: what exists, how the ranges differ, which one "
    "fits an application. Answers come from the published catalogue only."
)

EXAMPLES = [
    "What WiNtrip products do you have?",
    "What do you have for residential applications?",
    "Compare the WiNmaster ACB ranges.",
    "Which MCCB suits a 250 A feeder at 415 V?",
]


class _CancelOnDemand(BaseCallbackHandler):
    """Stop a turn at the next model, tool, or node boundary.

    Nothing else reaches inside a running graph: `graph.invoke` blocks on a
    worker thread, and LangGraph offers no way to interrupt it from outside.
    A callback does, because it runs on that thread — but only if it says so.
    LangChain catches whatever a handler raises and logs it as a handler fault
    unless `raise_error` is set, so that flag is the whole mechanism.

    A turn is a long chain of short steps — around sixty in a measured run — so
    this usually takes effect within a second. The worst case is one report
    generation, which cannot be broken into.
    """

    raise_error = True

    def __init__(self, flag: threading.Event) -> None:
        self.flag = flag

    def _check(self, *_args: Any, **_kwargs: Any) -> None:
        if self.flag.is_set():
            raise TurnCancelled()

    on_chain_start = _check
    on_llm_start = _check
    on_chat_model_start = _check
    on_tool_start = _check


def _progress(record: dict[str, Any]) -> str | None:
    """The one line a trace record deserves in the chat, if any.

    Most of a trace is bookkeeping — runnable spans, state snapshots, token
    counts — and belongs in the file it is already written to.
    """
    event = record.get("event")
    if event == "tool.start":
        return tool_phrase(record.get("tool") or "", record.get("inputs"))
    if event == "node.start":
        return agent_phrase(record.get("agent")) or node_phrase(record.get("node"))
    # The specialist subgraph's own nodes surface as runnables, not graph nodes.
    # `report` is the one worth showing: it is the longest generation in a turn.
    if event == "runnable.start" and record.get("name") == "report":
        return report_phrase(record.get("agent"))
    return None


def _step(title: str) -> gr.ChatMessage:
    return gr.ChatMessage(
        role="assistant", content="", metadata={"title": title, "status": "pending"}
    )


def _finish(step: gr.ChatMessage) -> None:
    """Mark a step complete — spinner to tick.

    Deliberately no duration. A step lasts until the next one starts, so the
    time against "Searching the catalogue" would be mostly the specialist
    reading the result, and a viewer would read it as a slow database.
    """
    step.metadata["status"] = "done"


def _ask(questions: list[str]) -> str:
    lines = "\n".join(f"- {question}" for question in questions)
    return f"Before I search, could you tell me:\n\n{lines}"


def _run_turn(text: str, state: dict[str, Any], events: queue.Queue) -> None:
    """Run one turn on a worker thread, reporting through ``events``.

    Owns the trace, so it also closes it: `run_question` only cleans up a trace
    it created itself.
    """
    trace = TraceLogger(listener=lambda record: events.put(("trace", record)))
    stopper = [_CancelOnDemand(state["cancel"])]
    try:
        if state.get("awaiting"):
            result = resume_question(
                text,
                thread_id=state["thread_id"],
                trace=trace,
                on_clarify=None,
                callbacks=stopper,
            )
        else:
            result = run_question(
                text,
                thread_id=state["thread_id"],
                session=state.get("session"),
                trace=trace,
                on_clarify=None,
                callbacks=stopper,
            )
        events.put(("result", result))
    except TurnCancelled:
        events.put(("cancelled", None))
    except BaseException as exc:  # noqa: BLE001 - reported into the chat
        events.put(("error", exc))
    finally:
        set_active_trace(None)
        trace.close()
        events.put(("done", None))


def _retire_previous(state: dict[str, Any]) -> None:
    """Make sure the last turn is finished before another starts.

    A cancelled turn frees the *page* at once, but its worker is still inside
    `graph.invoke` until the next boundary. Two of those at once would fight
    over `set_active_trace`, a module-level handle, and write to one
    checkpointer thread from two places.
    """
    worker = state.get("worker")
    if worker is None or not worker.is_alive():
        return
    flag = state.get("cancel")
    if flag is not None:
        flag.set()
    worker.join(timeout=120)


def respond(message: str, history: list[Any], state: dict[str, Any]):
    """Stream one turn into the chat: progress first, then the answer."""
    message = (message or "").strip()
    if not message:
        return
    state.setdefault("thread_id", str(uuid.uuid4()))
    _retire_previous(state)
    state["cancel"] = threading.Event()

    events: queue.Queue = queue.Queue()
    worker = threading.Thread(
        target=_run_turn, args=(message, state, events), daemon=True
    )
    state["worker"] = worker
    worker.start()

    steps: list[gr.ChatMessage] = []
    answer = ""
    result: dict[str, Any] | None = None
    error: BaseException | None = None
    cancelled = False

    def shown() -> list[gr.ChatMessage]:
        if not answer:
            return list(steps)
        return [*steps, gr.ChatMessage(role="assistant", content=answer)]

    while True:
        kind, payload = events.get()
        if kind == "done":
            break
        if kind == "result":
            result = payload
            continue
        if kind == "error":
            error = payload
            continue
        if kind == "cancelled":
            cancelled = True
            continue

        if payload.get("event") == "answer.delta":
            if steps and steps[-1].metadata.get("status") == "pending":
                _finish(steps[-1])
            answer += payload.get("text") or ""
            yield shown()
            continue

        line = _progress(payload)
        if not line or (steps and steps[-1].metadata.get("title") == line):
            continue
        if steps:
            _finish(steps[-1])
        steps.append(_step(line))
        yield shown()

    if steps and steps[-1].metadata.get("status") == "pending":
        _finish(steps[-1])

    if cancelled:
        note = "Stopped. Ask again, or start a new chat."
        yield [*steps, gr.ChatMessage(role="assistant", content=note)]
        return

    if error is not None:
        # The detail is kept rather than hidden: the terminal beside the window
        # has the trace, and a demonstration needs to be debuggable.
        note = f"That run failed: `{type(error).__name__}: {error}`"
        yield [*steps, gr.ChatMessage(role="assistant", content=note)]
        return

    questions = interrupt_questions(result or {})
    state["awaiting"] = bool(questions)
    if questions:
        # The turn is parked on the checkpoint; the next message resumes it, so
        # the session is deliberately left as it was.
        yield [*steps, gr.ChatMessage(role="assistant", content=_ask(questions))]
        return

    state["session"] = (result or {}).get("session")
    answer = answer or (result or {}).get("draft") or "No answer was produced."
    yield [*steps, gr.ChatMessage(role="assistant", content=answer)]


# Local families only — the artifact CSP aside, a demonstration machine may be
# offline, and a font fetched from a CDN would silently fall back to a serif.
SANS = [
    "ui-sans-serif",
    "system-ui",
    "-apple-system",
    "Segoe UI",
    "Roboto",
    "Helvetica Neue",
    "Arial",
    "sans-serif",
]
MONO = ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"]

CSS = f"""
/* Sans throughout, including the places a theme font does not reach: rendered
   markdown in the chat, and the code spans inside an answer. */
body, .gradio-container, .gradio-container *, .prose, .md {{
    font-family: {", ".join(SANS)} !important;
}}
.gradio-container code, .gradio-container pre, .md code, .md pre {{
    font-family: {", ".join(MONO)} !important;
}}

/* Progress steps. Gradio pins the step title to --text-sm with !important and
   fades the block to 0.8 opacity, which leaves it too faint to read across a
   room. These sit clearly below the answer in weight, but are legible. */
.thought-group .title .md,
.thought .title .md {{
    font-size: 0.9rem !important;
    line-height: 1.5 !important;
}}
.thought-group .title,
.thought .title {{
    color: var(--body-text-color) !important;
    font-weight: 500 !important;
    opacity: 1 !important;
}}
.thought-group .message-content,
.thought .message-content {{
    opacity: 1 !important;
}}
"""


def _role(item: Any) -> str:
    return item.get("role") if isinstance(item, dict) else getattr(item, "role", "")


def _content(item: Any) -> str:
    return item.get("content") if isinstance(item, dict) else getattr(item, "content", "")


def _submitted(text: str, history: list[Any]) -> tuple[str, list[Any]]:
    """Show the question and empty the box, before any model work starts."""
    text = (text or "").strip()
    if not text:
        return text, history
    return "", [*history, gr.ChatMessage(role="user", content=text)]


def _busy(busy: bool) -> tuple[Any, Any, Any, Any]:
    """Lock the page for the duration of a turn.

    Send stays where it is rather than being swapped out — a control that
    disappears reads as a fault, and the row jumping is the first thing an
    audience notices. Stop appears beside it, because a turn runs for about two
    minutes and a question asked by mistake should not have to be sat through.
    """
    return (
        gr.update(interactive=not busy),
        gr.update(interactive=not busy, value="Working…" if busy else "Send"),
        gr.update(visible=busy),
        gr.update(interactive=not busy),
    )


def _stop(state: dict[str, Any]) -> None:
    """Ask the running turn to unwind at its next boundary."""
    flag = state.get("cancel")
    if flag is not None:
        flag.set()


def _reset(state: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    """Start over: empty transcript, new thread, nothing carried across.

    A new `thread_id` is what makes it a genuinely fresh conversation — the
    checkpointer keys on it, so reusing one would let the old turns back in.
    """
    _retire_previous(state)
    return [], {}


def _reply(history: list[Any], state: dict[str, Any]):
    """Answer the question the chat is waiting on, streaming under it."""
    if not history or _role(history[-1]) != "user":
        # An empty submit, or a turn already answered. Nothing to do.
        yield history
        return
    for frame in respond(_content(history[-1]), history, state):
        yield [*history, *frame]


def build() -> gr.Blocks:
    theme = gr.themes.Soft(font=SANS, font_mono=MONO)
    with gr.Blocks(title=TITLE, theme=theme, css=CSS) as demo:
        with gr.Row():
            gr.Markdown(f"## {TITLE}\n{DESCRIPTION}")
            new_chat = gr.Button("New chat", scale=0, min_width=120)
        state = gr.State({})
        chatbot = gr.Chatbot(
            type="messages",
            height=560,
            show_label=False,
            # Answers are catalogue prose, not markup; render them as text.
            allow_tags=False,
        )
        with gr.Row():
            box = gr.Textbox(
                placeholder="Ask about a product, a range, or an application…",
                show_label=False,
                container=False,
                scale=9,
                autofocus=True,
            )
            send = gr.Button("Send", variant="primary", scale=1, min_width=110)
            stop = gr.Button(
                "Stop", variant="stop", scale=1, min_width=110, visible=False
            )
        gr.Examples(examples=EXAMPLES, inputs=box, label="Try one")

        locks = [box, send, stop, new_chat]
        replies = []
        for trigger in (box.submit, send.click):
            started = trigger(
                _submitted, [box, chatbot], [box, chatbot], queue=False
            ).then(lambda: _busy(True), None, locks, queue=False)
            reply = started.then(_reply, [chatbot, state], chatbot)
            reply.then(lambda: _busy(False), None, locks, queue=False)
            replies.append(reply)

        # `cancels` frees the page immediately; `_stop` is what actually ends
        # the work behind it, and it has to restore the controls itself because
        # cancelling takes the trailing handler with it.
        stop.click(_stop, [state], None, queue=False, cancels=replies).then(
            lambda: _busy(False), None, locks, queue=False
        )
        new_chat.click(_reset, [state], [chatbot, state], queue=False)
    # One turn at a time: the trace the model factory reports through is a
    # single module-level handle, so overlapping turns would interleave.
    demo.queue(default_concurrency_limit=1)
    return demo


def main() -> int:
    load_dotenv()
    demo = build()
    demo.launch(
        server_name=os.getenv("CS_UI_HOST", "127.0.0.1"),
        server_port=int(os.getenv("CS_UI_PORT", "7860")),
        share=os.getenv("CS_UI_SHARE", "").strip().lower() in {"1", "true", "yes"},
        show_api=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
