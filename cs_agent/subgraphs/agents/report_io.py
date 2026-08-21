"""TEMPORARY: dump the report call's exact input and output to a readable file.

Scratch instrumentation for a testing session, not part of the pipeline. To
remove it, delete this file and the two lines that reference it in `nodes.py`
(the import, and the `capture(...)` call at the end of `_generated`).

Off unless `CS_REPORT_IO` names a directory:

    CS_REPORT_IO=logs/report_io python -m cs_agent.cli "..."

One file per run per agent, appending each report call, in the same layout as
the captures already in `logs/report_io/` so the same eyeballing works.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AnyMessage

_LOCK = threading.Lock()
_CALLS: dict[str, int] = {}
# Whole messages, not excerpts: the point is to see exactly what the model saw.
RULE = "=" * 78
BANNER = "#" * 78


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _describe(index: int, message: AnyMessage) -> str:
    kind = type(message).__name__.replace("Message", "").upper()
    body = _text(message.content)
    head = f"[{index:02d}] {kind}"
    if name := getattr(message, "name", None):
        head += f"  name={name}"
    head += f"  ({len(body):,} chars)"
    if calls := getattr(message, "tool_calls", None):
        head += f"  tool_calls={[call.get('name') for call in calls]}"
    return head


def capture(
    agent: str,
    messages: list[AnyMessage],
    output: str,
    *,
    formatted: str = "",
    seconds: float | None = None,
    question: str = "",
) -> None:
    """Write one report call. Silent when CS_REPORT_IO is unset.

    ``output`` is what the model generated — the thing decode is paid for.
    ``formatted`` is the report after citations were expanded, which is what the
    gate and the composer actually read. Both, because the whole point of the
    change is that they are no longer the same size.
    """
    directory = (os.getenv("CS_REPORT_IO") or "").strip()
    if not directory:
        return
    path = Path(directory).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    target = path / f"{agent}.report_io.txt"

    with _LOCK:
        _CALLS[agent] = _CALLS.get(agent, 0) + 1
        index = _CALLS[agent]
        first = not target.exists()
        chars = sum(len(_text(m.content)) for m in messages)
        lines: list[str] = []
        if first and question:
            lines += [f"QUESTION: {question}", "", ""]
        lines += [
            BANNER,
            f"# REPORT CALL {index}  agent={agent!r}  {datetime.now():%H:%M:%S}",
            f"# input: {len(messages)} messages, {chars:,} chars (~{chars // 4:,} tokens)",
            f"# output: {len(output):,} chars (~{len(output) // 4:,} tokens)"
            + (
                f" in {seconds:.1f}s  ({len(output) // 4 / seconds:.1f} tok/s)"
                if seconds
                else ""
            ),
            BANNER,
            "",
        ]
        for position, message in enumerate(messages):
            lines += [RULE, _describe(position, message), RULE, _text(message.content), ""]
        lines += [RULE, f"MODEL OUTPUT — what decode paid for  ({len(output):,} chars)",
                  RULE, output, ""]
        if formatted:
            grew = len(formatted) - len(output)
            lines += [
                RULE,
                f"AFTER FORMATTING — what the composer reads  ({len(formatted):,} chars, "
                f"{grew:+,} from expansion)",
                RULE,
                formatted,
                "",
            ]
        lines += [""]
        with target.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
