"""Latency profiler for cs_agent trace files.

Splits a run's wall time into tool execution versus model time, and — when the
run used an Ollama endpoint — uses Ollama's own per-request counters to break
model time into load, prefill, and decode.

The effective prefill rate is the number to watch. A tool-calling loop re-sends
its whole transcript every turn, so `resend` below is normally several times 1.0;
that is inherent to the design and not itself a problem. What matters is whether
the server charges for those repeated tokens. Ollama counts cache hits in
prompt_eval_count but not in prompt_eval_duration, so a rate far above the
cold-start rate means the KV prefix cache is working, and a rate close to it
means something is invalidating the prefix every turn.

Usage:
    python latency_profile.py logs/some_run.jsonl
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

NS = 1_000_000_000


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _find_ollama_meta(node, out: list[dict]) -> None:
    if isinstance(node, dict):
        if "prompt_eval_count" in node:
            out.append(node)
        for value in node.values():
            _find_ollama_meta(value, out)
    elif isinstance(node, list):
        for value in node:
            _find_ollama_meta(value, out)


def _stage_of(messages: object) -> str:
    """Name the pipeline stage a call belongs to, from its system prompt.

    The split that matters is the specialist's tool loop against its report
    call: they run the same model on nearly the same text, and on the run this
    was written for the report was 48% of all model time.
    """
    flat = messages
    while isinstance(flat, list) and flat and isinstance(flat[0], list):
        flat = flat[0]
    if not isinstance(flat, list):
        return "?"
    system = " ".join(
        str(m.get("content") or "")
        for m in flat
        if isinstance(m, dict) and m.get("type") == "system"
    )
    # The whole last message, not a slice of it: the report node puts its
    # instruction and the schema there, and the schema JSON is long enough that
    # any fixed-size window off the end misses the wording that identifies it.
    tail = " ".join(
        str(m.get("content") or "") for m in flat[-1:] if isinstance(m, dict)
    )
    # Match the report node's own instruction, which is worded the same before
    # and after that node was folded into the specialist's thread, so old and
    # new runs stay comparable. Matching a looser "specialist report" would also
    # catch both composer prompts, which talk *about* specialist reports.
    produced = "Produce the specialist report"
    if produced in system or produced in tail:
        return "specialist report"
    # `structured` retries by appending its validation error, so a retry's last
    # message is the error, not the instruction. Without this the retry — often
    # the call that actually produces the report — lands in the loop's bucket.
    if "Invalid output. Fix these errors" in tail:
        return "specialist report" if "You are one specialist" in system else "retry"
    if "You are one specialist" in system:
        return "specialist report" if "JSON Schema" in tail else "specialist loop"
    if "Write the final answer" in system:
        return "compose_final"
    if "enough evidence" in system:
        return "composer sufficiency"
    if "Ask at most" in system:
        return "clarify"
    if "JSON Schema" in system:
        return "intake / planner"
    return "other"


def _merged_seconds(spans: list[tuple[datetime, datetime]]) -> float:
    """Union of intervals, so parallel specialists are not double counted."""
    total = 0.0
    start = end = None
    for span_start, span_end in sorted(spans):
        if start is None:
            start, end = span_start, span_end
        elif span_start <= end:
            end = max(end, span_end)
        else:
            total += (end - start).total_seconds()
            start, end = span_start, span_end
    if start is not None:
        total += (end - start).total_seconds()
    return total


def profile(path: Path) -> None:
    question = None
    stamps: list[datetime] = []
    open_tools: dict[str, dict] = {}
    open_llm: dict[str, datetime] = {}
    tool_spans: list[dict] = []
    llm_spans: list[tuple[datetime, datetime]] = []
    ollama_calls: list[dict] = []

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            event = record.get("event")
            run_id = str(record.get("callback_run_id"))
            if timestamp := record.get("timestamp"):
                stamps.append(_parse_ts(timestamp))
            if event == "run.start":
                question = record.get("question")

            if event == "tool.start":
                open_tools[run_id] = {
                    "ts": _parse_ts(record["timestamp"]),
                    "tool": record.get("tool"),
                    "agent": record.get("agent"),
                    "input": json.dumps(
                        record.get("inputs") or record.get("input"), default=str
                    ),
                }
            elif event in {"tool.end", "tool.error"}:
                start = open_tools.pop(run_id, None)
                if start:
                    end = _parse_ts(record["timestamp"])
                    tool_spans.append(
                        {
                            **start,
                            "end": end,
                            "seconds": (end - start["ts"]).total_seconds(),
                            "out_chars": len(
                                json.dumps(record.get("output"), default=str)
                            ),
                        }
                    )
            elif event == "llm.start":
                open_llm[run_id] = (
                    _parse_ts(record["timestamp"]),
                    _stage_of(record.get("messages")),
                )
            elif event in {"llm.end", "llm.error"}:
                opened = open_llm.pop(run_id, None)
                start_ts, stage = opened if opened else (None, "?")
                if start_ts:
                    llm_spans.append((start_ts, _parse_ts(record["timestamp"])))
                if event == "llm.end":
                    found: list[dict] = []
                    _find_ollama_meta(record.get("response"), found)
                    if found:
                        meta = found[0]
                        ollama_calls.append(
                            {
                                "stage": stage,
                                "agent": record.get("agent") or "-",
                                "prompt_tokens": meta.get("prompt_eval_count") or 0,
                                "output_tokens": meta.get("eval_count") or 0,
                                "load_s": (meta.get("load_duration") or 0) / NS,
                                "prefill_s": (meta.get("prompt_eval_duration") or 0) / NS,
                                "decode_s": (meta.get("eval_duration") or 0) / NS,
                                "total_s": (meta.get("total_duration") or 0) / NS,
                            }
                        )

    wall = (max(stamps) - min(stamps)).total_seconds() if stamps else 0.0
    tool_wall = _merged_seconds([(span["ts"], span["end"]) for span in tool_spans])
    llm_wall = _merged_seconds(llm_spans)

    print(f"file: {path}")
    if question:
        print(f"question: {question}")
    print(f"wall clock: {wall:.1f}s")
    print()
    print(f"{'':<14}{'calls':>7}{'wall s':>10}{'% wall':>9}")
    print(f"{'model':<14}{len(llm_spans):>7}{llm_wall:>10.1f}{llm_wall / wall * 100:>8.1f}%")
    print(f"{'tools':<14}{len(tool_spans):>7}{tool_wall:>10.1f}{tool_wall / wall * 100:>8.1f}%")

    if tool_spans:
        print()
        print("tool execution and payload size")
        print(f"{'tool':<24}{'n':>4}{'exec_s':>9}{'mean_s':>8}{'max_s':>8}{'out_chars':>12}")
        by_tool: dict[str, list[dict]] = defaultdict(list)
        for span in tool_spans:
            by_tool[str(span["tool"])].append(span)
        for name, spans in sorted(
            by_tool.items(), key=lambda item: -sum(s["seconds"] for s in item[1])
        ):
            seconds = [span["seconds"] for span in spans]
            print(
                f"{name:<24}{len(spans):>4}{sum(seconds):>9.2f}"
                f"{sum(seconds) / len(spans):>8.2f}{max(seconds):>8.2f}"
                f"{sum(span['out_chars'] for span in spans):>12,}"
            )

        repeats: dict[tuple, list[dict]] = defaultdict(list)
        for span in tool_spans:
            repeats[(span["tool"], span["input"])].append(span)
        wasted = sum(
            sum(span["out_chars"] for span in spans[1:])
            for spans in repeats.values()
            if len(spans) > 1
        )
        if wasted:
            print(f"duplicate tool calls re-sent {wasted:,} chars of identical payload")

    if not ollama_calls:
        return

    print()
    print("model time (Ollama server-side counters)")
    load = sum(call["load_s"] for call in ollama_calls)
    prefill = sum(call["prefill_s"] for call in ollama_calls)
    decode = sum(call["decode_s"] for call in ollama_calls)
    total = sum(call["total_s"] for call in ollama_calls)
    for label, value in (
        ("load", load),
        ("prefill", prefill),
        ("decode", decode),
        ("other", total - load - prefill - decode),
    ):
        print(f"  {label:<10}{value:>9.1f}s{value / total * 100:>7.1f}%")
    print(f"  {'TOTAL':<10}{total:>9.1f}s")

    by_stage: dict[str, list[dict]] = defaultdict(list)
    for call in ollama_calls:
        by_stage[call["stage"]].append(call)
    print()
    print("model time by stage")
    print(
        f"{'stage':<22}{'n':>4}{'wall_s':>9}{'prefill':>9}{'decode':>9}"
        f"{'in_tok':>11}{'out_tok':>9}"
    )
    for stage, calls in sorted(
        by_stage.items(), key=lambda item: -sum(c["total_s"] for c in item[1])
    ):
        print(
            f"{stage:<22}{len(calls):>4}"
            f"{sum(c['total_s'] for c in calls):>9.1f}"
            f"{sum(c['prefill_s'] for c in calls):>9.1f}"
            f"{sum(c['decode_s'] for c in calls):>9.1f}"
            f"{sum(c['prompt_tokens'] for c in calls):>11,}"
            f"{sum(c['output_tokens'] for c in calls):>9,}"
        )

    prompt_tokens = sum(call["prompt_tokens"] for call in ollama_calls)
    output_tokens = sum(call["output_tokens"] for call in ollama_calls)
    print()
    print(
        f"prompt tokens {prompt_tokens:,} at {prompt_tokens / prefill:,.0f} tok/s; "
        f"output tokens {output_tokens:,} at {output_tokens / decode:,.0f} tok/s"
    )

    print()
    print("prefix reuse per conversation")
    print(f"{'agent':<20}{'calls':>6}{'sum_tok':>11}{'peak_tok':>10}{'resend':>8}{'tok/s':>9}")
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for call in ollama_calls:
        by_agent[call["agent"]].append(call)
    for agent, calls in sorted(
        by_agent.items(), key=lambda item: -sum(c["prefill_s"] for c in item[1])
    ):
        summed = sum(call["prompt_tokens"] for call in calls)
        peak = max(call["prompt_tokens"] for call in calls)
        spent = sum(call["prefill_s"] for call in calls)
        print(
            f"{agent:<20}{len(calls):>6}{summed:>11,}{peak:>10,}"
            f"{summed / peak:>7.1f}x{summed / spent if spent else 0:>9,.0f}"
        )

    # The first call of a run cannot hit the cache, so its rate is the local
    # floor to compare the aggregate against. It has to be the first one
    # chronologically, not the quickest: once caching works the quickest call is
    # a cache hit, and using it as the "uncached" baseline reports every healthy
    # run as broken. Calls with a trivial prompt are skipped because per-request
    # overhead, not prefill, sets their rate.
    cold = next(
        (call for call in ollama_calls if call["prompt_tokens"] >= 500),
        ollama_calls[0],
    )
    cold_rate = (
        cold["prompt_tokens"] / cold["prefill_s"] if cold["prefill_s"] else 0.0
    )
    rate = prompt_tokens / prefill
    print()
    print(f"effective prefill {rate:,.0f} tok/s vs {cold_rate:,.0f} tok/s uncached")
    print(
        "verdict: prefix cache is "
        + ("working" if rate > cold_rate * 1.8 else "MISSING - check for a mutating prompt prefix")
    )

    contended = _merged_seconds(
        [
            (start, end)
            for index, (start, end) in enumerate(llm_spans)
            if any(
                other_start < end and start < other_end
                for other_start, other_end in llm_spans[index + 1 :]
            )
        ]
    )
    if contended:
        print(
            f"note: {contended:.0f}s ({contended / wall * 100:.0f}% of the run) had "
            "concurrent model calls competing for server slots"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="trace JSONL file")
    profile(parser.parse_args().path)
