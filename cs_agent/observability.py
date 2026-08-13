"""Structured execution tracing for LangGraph and LangChain."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel

from cs_agent.tool_errors import TOOL_FAILURE_LIMIT


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
    fields = ("sku_code", "spec_id", "category", "family", "level", "code")
    return [f"{field}={item[field]}" for field in fields if item.get(field) is not None]


def _summarize_tool_output(raw: Any) -> str:
    value = _parse_json_string(raw)
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
        if plan.get("categories"):
            parts.append("categories=" + ", ".join(map(str, plan["categories"])))
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
        lines.append(f"completed tool calls: {update['tool_calls_made']}/12")
    if update.get("tool_failures"):
        lines.append(
            f"failed tool calls: {update['tool_failures']}/{TOOL_FAILURE_LIMIT}"
        )
    if "clarify_count" in update:
        lines.append(f"clarification rounds: {update['clarify_count']}/2")
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


class TraceLogger:
    """Append trace events to JSONL and optionally mirror them to stdout."""

    def __init__(
        self,
        *,
        run_id: str | None = None,
        file_path: str | Path | None = None,
        print_to_screen: bool | None = None,
    ) -> None:
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
        self._stream = self.file_path.open("a", encoding="utf-8")
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

    @staticmethod
    def _print_record(record: dict[str, Any]) -> None:
        """Render concise progress while the file retains the complete JSON event."""
        event = record["event"]
        if event == "run.start":
            print(f"\n▶ Question: {record.get('question', '')}", flush=True)
            print(f"  Trace: {record.get('log_file', '')}", flush=True)
        elif event == "node.transition":
            print(
                f"→ {record.get('from_node', '?')} → {record.get('to_node', '?')}",
                flush=True,
            )
        elif event == "state.update":
            node = record.get("node", "state")
            for line in _summarize_state_update(record.get("update")):
                print(f"  [{node}] {line}", flush=True)
        elif event == "tool.start":
            inputs = record.get("inputs")
            if inputs in (None, {}):
                inputs = record.get("input")
            print(
                f"  🔧 {record.get('tool') or 'tool'}({_short(inputs, 320)})",
                flush=True,
            )
        elif event == "tool.end":
            print(
                f"  ✓ {record.get('tool') or 'tool'}: "
                f"{_summarize_tool_output(record.get('output'))}",
                flush=True,
            )
        elif event in {"tool.error", "llm.error", "runnable.error", "node.error"}:
            name = record.get("tool") or record.get("node") or event.split(".", 1)[0]
            print(f"  ✗ {name}: {_short(record.get('error'), 240)}", flush=True)
        elif event == "run.interrupt":
            payload = record.get("payload")
            questions = payload.get("questions") if isinstance(payload, dict) else payload
            count = len(questions) if isinstance(questions, list) else 1
            print(f"  ⏸ Waiting for clarification ({count} question(s))", flush=True)
        elif event == "run.resume":
            print("  ▶ Clarification received; resuming", flush=True)
        elif event == "run.end":
            status = record.get("status", "unknown")
            symbol = "✓" if status == "completed" else "✗"
            print(f"{symbol} Run {status}", flush=True)
        # Intentionally suppress snapshots, full LLM payloads, runnable callbacks,
        # node start/end events, and duplicate agent.change events on the terminal.

    def close(self) -> None:
        with self._lock:
            if not self._stream.closed:
                self._stream.close()


class AgentCallbackHandler(BaseCallbackHandler):
    """Capture LangChain model, tool, and runnable lifecycle events."""

    def __init__(self, trace: TraceLogger) -> None:
        self.trace = trace
        self._tool_names: dict[uuid.UUID, str] = {}
        self._tool_lock = threading.Lock()

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
            error=error,
        )
