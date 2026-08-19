"""Structured execution tracing for LangGraph and LangChain."""

from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import ensure_config
from pydantic import BaseModel

from cs_agent.config.limits import get_limits
from cs_agent.contracts import brief_depth
from cs_agent.tool_errors import TOOL_FAILURE_LIMIT

AGENT_METADATA_KEY = "cs_agent"


def agent_scoped_config(
    label: str, config: RunnableConfig | None = None
) -> RunnableConfig:
    """Tag everything run under `label` so traces name the calling sub-agent.

    Nested scopes are joined with `/`, so SQL issued by the analytics subgraph on
    behalf of the coverage specialist is labelled `coverage/analytics`.
    """
    metadata = dict(ensure_config(config).get("metadata") or {})
    parent = metadata.get(AGENT_METADATA_KEY)
    metadata[AGENT_METADATA_KEY] = f"{parent}/{label}" if parent else label
    return {"metadata": metadata}


def _agent_from_metadata(metadata: Any) -> str | None:
    if isinstance(metadata, dict) and metadata.get(AGENT_METADATA_KEY):
        return str(metadata[AGENT_METADATA_KEY])
    return None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, BaseException):
        return {"type": type(value).__name__, "message": str(value)}
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "model_dump"):
        try:
            return _jsonable(value.model_dump(mode="json"))
        except Exception:
            pass
    return repr(value)


def _parse_json_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _short(value: Any, limit: int = 240) -> str:
    """Render a compact terminal value without changing JSONL detail."""
    value = _parse_json_string(value)
    if isinstance(value, str):
        text = " ".join(value.split())
    else:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _identifiers(item: Any) -> list[str]:
    if not isinstance(item, dict):
        return []
    fields = ("sku_code", "spec_id", "family", "path", "level", "code", "agent")
    return [f"{field}={item[field]}" for field in fields if item.get(field) is not None]


def _summarize_tool_output(raw: Any) -> str:
    value = _parse_json_string(raw)
    if isinstance(value, dict) and "tool_call_id" in value and "content" in value:
        # ToolNode reports the wrapping ToolMessage; the payload is its content.
        value = _parse_json_string(value["content"])
    if isinstance(value, dict):
        if value.get("error"):
            return f"error: {_short(value['error'], 180)}"
        parts = _identifiers(value)
        for key in ("row_count", "sku_count", "fact_count"):
            if value.get(key) is not None:
                parts.append(f"{key}={value[key]}")
        for key in ("rows", "facts", "specs", "categories", "families", "content"):
            if isinstance(value.get(key), list):
                parts.append(f"{key}={len(value[key])}")
        if value.get("axes") and isinstance(value["axes"], dict):
            parts.append("axes=" + ",".join(value["axes"].keys()))
        if parts:
            return ", ".join(parts)
        return f"object with {len(value)} fields"
    if isinstance(value, list):
        samples: list[str] = []
        for item in value[:3]:
            identity = ", ".join(_identifiers(item))
            if identity:
                samples.append(identity)
        suffix = f"; first: {' | '.join(samples)}" if samples else ""
        return f"{len(value)} result(s){suffix}"
    return _short(value, 180)


def _summarize_state_update(update: Any) -> list[str]:
    if not isinstance(update, dict):
        return [_short(update)]
    lines: list[str] = []
    plan = update.get("plan")
    if isinstance(plan, dict):
        parts = [f"intent={plan.get('intent', '?')}"]
        if plan.get("dispatch"):
            by_stage: dict[int, list[str]] = {}
            for brief in plan["dispatch"]:
                # Depth drives how much retrieval a brief is allowed, so it is
                # worth seeing beside the agent when reading a trace back.
                by_stage.setdefault(int(brief.get("stage", 1) or 1), []).append(
                    f"{brief.get('agent', '?')}[{brief_depth(brief)}]"
                )
            parts.append(
                "agents="
                + " -> ".join(
                    ", ".join(by_stage[stage]) for stage in sorted(by_stage)
                )
            )
        if plan.get("open_params"):
            parts.append("open=" + ", ".join(map(str, plan["open_params"])))
        parts.append(f"clarify={bool(plan.get('needs_clarification'))}")
        lines.append("plan: " + "; ".join(parts))
    evidence = update.get("evidence")
    if isinstance(evidence, list):
        identities: list[str] = []
        for item in evidence[:3]:
            identity = ", ".join(_identifiers(item))
            if identity:
                identities.append(identity)
        suffix = f" ({' | '.join(identities)})" if identities else ""
        lines.append(f"evidence: +{len(evidence)} record(s){suffix}")
    if "tool_calls_made" in update:
        lines.append(
            "completed tool calls: "
            f"{update['tool_calls_made']}/{get_limits().global_tool_budget}"
        )
    if update.get("tool_failures"):
        lines.append(
            f"failed tool calls: {update['tool_failures']}/{TOOL_FAILURE_LIMIT}"
        )
    if "clarify_count" in update:
        lines.append(
            "clarification rounds: "
            f"{update['clarify_count']}/{get_limits().clarify_rounds}"
        )
    if update.get("assumptions"):
        lines.append("assumptions: " + _short(update["assumptions"], 180))
    if update.get("draft") is not None:
        lines.append(f"draft ready: {len(str(update['draft']))} characters")
    validation = update.get("validation")
    if isinstance(validation, dict):
        lines.append(
            "validation: "
            f"{'passed' if validation.get('passed') else 'failed'}; "
            f"matched={validation.get('matched', 0)}/"
            f"{validation.get('numbers_total', 0)}; "
            f"action={validation.get('action', '?')}"
        )
        if validation.get("unmatched"):
            lines.append("unmatched: " + _short(validation["unmatched"], 160))
    messages = update.get("messages")
    if isinstance(messages, list):
        tool_names: list[str] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            calls = message.get("tool_calls") or message.get("additional_kwargs", {}).get(
                "tool_calls", []
            )
            for call in calls or []:
                if isinstance(call, dict):
                    name = call.get("name") or call.get("function", {}).get("name")
                    if name:
                        tool_names.append(str(name))
        if tool_names:
            lines.append("requested tools: " + ", ".join(tool_names))
    return lines or ["updated: " + ", ".join(update.keys())]


# Paths already truncated by this process. A trace covers one process, not one
# question: an interactive session builds a fresh TraceLogger per turn, so
# truncating on every construction would discard the earlier turns of the same
# conversation. Truncate the first time a path is opened, append afterwards.
_TRUNCATED_PATHS: set[Path] = set()
_TRUNCATE_LOCK = threading.Lock()


def _open_trace_stream(path: Path):
    """Open ``path`` for writing, truncating only on this process's first use."""
    with _TRUNCATE_LOCK:
        mode = "a" if path in _TRUNCATED_PATHS else "w"
        _TRUNCATED_PATHS.add(path)
    return path.open(mode, encoding="utf-8")


class TraceLogger:
    """Write trace events to JSONL and optionally mirror them to stdout."""

    def __init__(
        self,
        *,
        run_id: str | None = None,
        file_path: str | Path | None = None,
        print_to_screen: bool | None = None,
        listener: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        # A second reader of the same events, for a frontend that has to show
        # progress while a two-minute turn runs. It is handed each record after
        # the file and the screen have had it, so attaching one cannot change
        # what either of those sees. It runs on the emitting thread, inside the
        # lock that orders the screen, so it must be cheap — a queue put, not
        # work. Nothing in the graph knows it exists.
        self.listener = listener
        self.run_id = run_id or str(uuid.uuid4())
        configured_path = file_path or os.getenv(
            "CS_LOG_FILE", "logs/cs_agent_trace.jsonl"
        )
        self.file_path = Path(configured_path).expanduser()
        self.print_to_screen = (
            _env_bool("CS_LOG_TO_SCREEN", True)
            if print_to_screen is None
            else print_to_screen
        )
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = _open_trace_stream(self.file_path)
        self._lock = threading.Lock()

    def event(self, event: str, **details: Any) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": self.run_id,
            "event": event,
            **{key: _jsonable(value) for key, value in details.items()},
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self._stream.write(line + "\n")
            self._stream.flush()
            if self.print_to_screen:
                self._print_record(record)
            if self.listener is not None:
                self.listener(record)

    def notify(self, event: str, **details: Any) -> None:
        """Send a record to the listener alone — not to the file or the screen.

        For output the trace deliberately does not log. Streamed answer text is
        the case: `llm.end` already records it whole, and repeating it per
        fragment would bloat every trace, but a chat window still needs the
        fragments as they arrive.
        """
        if self.listener is None:
            return
        with self._lock:
            self.listener({"run_id": self.run_id, "event": event, **details})

    def write(self, text: str, *, end: str = "\n") -> None:
        """Print streamed model output, if the screen is in use.

        Takes the same lock as `event`, because specialists stream in parallel
        and their lines share the terminal with node progress. Deliberately not
        written to the JSONL: `llm.end` already records the full response, and
        duplicating it per line would double the size of every trace.

        `end=""` is for the final answer, which streams as raw text and is left
        to the terminal to wrap.
        """
        if not self.print_to_screen:
            return
        with self._lock:
            print(text, end=end, flush=True)

    @staticmethod
    def _print_record(record: dict[str, Any]) -> None:
        """Render concise progress while the file retains the complete JSON event."""
        event = record["event"]
        agent = record.get("agent")
        # Sub-agents fan out in parallel, so every line names its owner.
        scope = f"[{agent}] " if agent else ""
        if event == "run.start":
            print(f"\n▶ Question: {record.get('question', '')}", flush=True)
            print(f"  Trace: {record.get('log_file', '')}", flush=True)
        elif event == "node.transition":
            origin = record.get("from_node", "?")
            if agent:
                origin = f"{origin}[{agent}]"
            print(f"→ {origin} → {record.get('to_node', '?')}", flush=True)
        elif event == "node.start":
            if agent:
                print(f"  ▷ [{record.get('node', 'node')}:{agent}] started", flush=True)
        elif event == "state.update":
            node = record.get("node", "state")
            label = f"{node}:{agent}" if agent else node
            for line in _summarize_state_update(record.get("update")):
                print(f"  [{label}] {line}", flush=True)
        elif event == "tool.start":
            inputs = record.get("inputs")
            if inputs in (None, {}):
                inputs = record.get("input")
            print(
                f"  {scope}🔧 {record.get('tool') or 'tool'}({_short(inputs, 320)})",
                flush=True,
            )
        elif event == "tool.end":
            print(
                f"  {scope}✓ {record.get('tool') or 'tool'}: "
                f"{_summarize_tool_output(record.get('output'))}",
                flush=True,
            )
        elif event in {
            "llm.context_overflow",
            "llm.context_pressure",
            "llm.prompt_truncated",
        }:
            # Silent truncation is the failure this project can least afford to
            # miss, so it prints even though other llm.* events are suppressed.
            symbol = "⚠" if event == "llm.context_pressure" else "‼"
            node = record.get("node") or "model"
            if event == "llm.prompt_truncated":
                detail = (
                    f"prompt truncated by Ollama: evaluated "
                    f"{record.get('prompt_eval_count')} of {record.get('num_ctx')} "
                    "context tokens"
                )
            else:
                detail = (
                    f"~{record.get('estimated_prompt_tokens')} prompt tokens vs "
                    f"{record.get('usable_prompt_tokens')} usable "
                    f"(num_ctx {record.get('num_ctx')}); tools "
                    f"~{record.get('estimated_tool_schema_tokens')}"
                )
            print(f"  {scope}{symbol} [{node}] {detail}", flush=True)
        elif event in {"tool.error", "llm.error", "runnable.error", "node.error"}:
            name = record.get("tool") or record.get("node") or event.split(".", 1)[0]
            print(f"  {scope}✗ {name}: {_short(record.get('error'), 240)}", flush=True)
        elif event == "run.interrupt":
            payload = record.get("payload")
            questions = payload.get("questions") if isinstance(payload, dict) else payload
            count = len(questions) if isinstance(questions, list) else 1
            print(f"  ⏸ Waiting for clarification ({count} question(s))", flush=True)
        elif event == "run.resume":
            print("  ▶ Clarification received; resuming", flush=True)
        elif event == "run.end":
            status = record.get("status", "unknown")
            # A cancelled run is not a failed one; ✗ next to it reads as a bug.
            symbol = {"completed": "✓", "cancelled": "⏹"}.get(status, "✗")
            print(f"{symbol} Run {status}", flush=True)
        # Intentionally suppress snapshots, full LLM payloads, runnable callbacks,
        # node start/end events, and duplicate agent.change events on the terminal.

    def close(self) -> None:
        with self._lock:
            if not self._stream.closed:
                self._stream.close()


_ACTIVE_TRACE: TraceLogger | None = None


def set_active_trace(trace: TraceLogger | None) -> None:
    """Register the trace that code below LangGraph should report through.

    The model factory never sees a RunnableConfig, so it has no callback to
    write on, and this project configures no logging handlers — a
    ``logger.warning`` there would go nowhere. One process runs one trace at a
    time, so a module-level handle is enough to keep its warnings in the file
    the user actually reads.
    """
    global _ACTIVE_TRACE
    _ACTIVE_TRACE = trace


def active_trace() -> TraceLogger | None:
    return _ACTIVE_TRACE


class AgentCallbackHandler(BaseCallbackHandler):
    """Capture LangChain model, tool, and runnable lifecycle events."""

    def __init__(self, trace: TraceLogger) -> None:
        self.trace = trace
        self._tool_names: dict[uuid.UUID, str] = {}
        self._run_agents: dict[uuid.UUID, str] = {}
        self._tool_lock = threading.Lock()

    def _enter(
        self,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None,
        metadata: Any,
    ) -> str | None:
        """Resolve the owning sub-agent, inheriting it from the parent run."""
        agent = _agent_from_metadata(metadata)
        with self._tool_lock:
            if agent is None and parent_run_id is not None:
                agent = self._run_agents.get(parent_run_id)
            if agent:
                self._run_agents[run_id] = agent
        return agent

    def _exit(self, run_id: uuid.UUID) -> str | None:
        with self._tool_lock:
            return self._run_agents.pop(run_id, None)

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.trace.event(
            "llm.start",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
            agent=self._enter(run_id, parent_run_id, kwargs.get("metadata")),
            model=serialized,
            messages=messages,
            metadata=kwargs.get("metadata"),
            invocation_params=kwargs.get("invocation_params"),
        )

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.trace.event(
            "llm.end",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
            agent=self._exit(run_id),
            response=response,
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.trace.event(
            "llm.error",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
            agent=self._exit(run_id),
            error=error,
        )

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name") or str(kwargs.get("name") or "tool")
        with self._tool_lock:
            self._tool_names[run_id] = tool_name
        self.trace.event(
            "tool.start",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
            agent=self._enter(run_id, parent_run_id, kwargs.get("metadata")),
            tool=tool_name,
            input=input_str,
            inputs=kwargs.get("inputs"),
            metadata=kwargs.get("metadata"),
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        with self._tool_lock:
            tool_name = self._tool_names.pop(run_id, None)
        self.trace.event(
            "tool.end",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
            agent=self._exit(run_id),
            tool=tool_name or kwargs.get("name"),
            output=output,
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        with self._tool_lock:
            tool_name = self._tool_names.pop(run_id, None)
        self.trace.event(
            "tool.error",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
            agent=self._exit(run_id),
            tool=tool_name or kwargs.get("name"),
            error=error,
        )

    def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: dict[str, Any],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.trace.event(
            "runnable.start",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
            agent=self._enter(run_id, parent_run_id, kwargs.get("metadata")),
            name=kwargs.get("name"),
            serialized=serialized,
            inputs=inputs,
            metadata=kwargs.get("metadata"),
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.trace.event(
            "runnable.end",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
            agent=self._exit(run_id),
            outputs=outputs,
        )

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.trace.event(
            "runnable.error",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
            agent=self._exit(run_id),
            error=error,
        )
