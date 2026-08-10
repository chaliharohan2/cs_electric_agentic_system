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
        """Render a readable terminal block while the file stays valid JSONL."""
        event = record["event"]
        timestamp = record["timestamp"]
        run_id = record["run_id"]
        details = {
            key: value
            for key, value in record.items()
            if key not in {"event", "timestamp", "run_id"}
        }
        print(f"\n[TRACE] {event}", flush=False)
        print(f"  time: {timestamp}", flush=False)
        print(f"  run:  {run_id}", flush=False)
        if details:
            formatted = json.dumps(details, ensure_ascii=False, indent=2)
            print("  details:", flush=False)
            print(
                "\n".join(f"    {line}" for line in formatted.splitlines()),
                flush=False,
            )
        print("-" * 80, flush=True)

    def close(self) -> None:
        with self._lock:
            if not self._stream.closed:
                self._stream.close()


class AgentCallbackHandler(BaseCallbackHandler):
    """Capture LangChain model, tool, and runnable lifecycle events."""

    def __init__(self, trace: TraceLogger) -> None:
        self.trace = trace

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
        self.trace.event(
            "tool.start",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
            tool=serialized.get("name"),
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
        self.trace.event(
            "tool.end",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
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
        self.trace.event(
            "tool.error",
            callback_run_id=run_id,
            parent_run_id=parent_run_id,
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
