"""Run the same questions through every specialist-report mode and compare.

The report node is 43-56% of a turn's wall time on this server and almost all of
that is decode, so anything that stops a model writing the report is worth a
large fraction of the turn. What is not obvious from a profile is what the
answer loses, and that is what this harness is for: it runs each mode over the
same question set, records where the time went, and puts the final answers side
by side so the trade can be read rather than assumed.

Each run is a fresh subprocess. The specialist graph, the limits and the model
clients are all cached per process, and a mode switch has to be seen by all
three.

    python bench_report_modes.py                       # every mode, every question
    python bench_report_modes.py --modes llm,raw       # a subset
    python bench_report_modes.py --report              # re-aggregate what is on disk
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from latency_profile import _find_ollama_meta, _parse_ts, _stage_of  # noqa: E402

OUT = Path(os.getenv("CS_BENCH_OUT", "logs/bench"))
MODES = ["llm", "derived", "raw", "auto"]

QUESTIONS: dict[str, str] = {
    # One tool call, 2,395 chars back, and the report that described it came to
    # 7,440. The cheapest turn in the sample and the most wasteful report.
    "wintrip": "List the wintrip products.",
    # An overview that has to walk rather than look up: several payloads, so the
    # derived modes have to choose between families nothing marks as relevant.
    "residential": "What do you have for residential applications?",
    # Detailed depth, `get_sku` payloads of ~26,000 chars each. The case where
    # passing the retrieval on untouched is most likely to break.
    "changeover": (
        "I need a 400A 4-pole on-load changeover switch, compact footprint "
        "— what do you have?"
    ),
    # The comparison table is the one report field a tool returns already in the
    # shape the schema wants.
    "compare": "Compare the WiNmaster ACB ranges.",
}


OLLAMA_PS = "http://192.168.0.147:11434/api/ps"

# Per-cell ceiling. The comparison question ran to 508s under `llm` and past
# 1800s under `lean`, so this is headroom rather than a target; a cell that
# reaches it is recorded as a failure and the suite carries on.
CELL_TIMEOUT = int(os.getenv("CS_BENCH_CELL_TIMEOUT", "2700"))

# How far a cell's decode rate may drift from the calibration probe before its
# numbers stop being comparable to the rest of the table. The modes differ in
# how much of their work is decode versus prefill, so a server whose decode is
# degraded does not slow every mode by the same fraction — it slows the ones
# that decode most, which is exactly the axis under test. 15% is tight enough
# to catch a second model landing in VRAM, loose enough to ignore noise.
DRIFT = 0.15


def _resident() -> list[str]:
    """Models Ollama currently holds in VRAM, or nothing if it cannot be asked."""
    try:
        import urllib.request

        with urllib.request.urlopen(OLLAMA_PS, timeout=5) as response:
            return [
                model.get("name", "?")
                for model in json.loads(response.read()).get("models", [])
            ]
    except Exception:
        return []


def _preflight(expect: str) -> None:
    """Refuse to start a run that will not be comparable to itself.

    A second 27B model resident alongside this one took decode on this box from
    38 tok/s to 12.5 while leaving prefill untouched, which flatters every mode
    that trades decode for prefill. That is the measurement this harness exists
    to make, so it is not something to discover afterwards in the numbers.
    """
    resident = _resident()
    others = [name for name in resident if expect.split(":")[0] not in name]
    if others:
        print(
            f"!! {len(others)} other model(s) resident in VRAM: {', '.join(others)}.\n"
            f"   Decode will be degraded and the comparison between modes will be\n"
            f"   distorted, not merely slowed. Unload them, or pass --force.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _rates(trace: Path) -> tuple[float, float]:
    """Decode and prefill rates for a finished run, in tokens per second."""
    out = dec = pin = pre = 0.0
    if not trace.exists():
        return 0.0, 0.0
    for line in trace.open(encoding="utf-8"):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("event") != "llm.end":
            continue
        found: list[dict] = []
        _find_ollama_meta(record.get("response"), found)
        if not found:
            continue
        meta = found[0]
        out += meta.get("eval_count") or 0
        dec += (meta.get("eval_duration") or 0) / 1e9
        pin += meta.get("prompt_eval_count") or 0
        pre += (meta.get("prompt_eval_duration") or 0) / 1e9
    return (out / dec if dec else 0.0), (pin / pre if pre else 0.0)


def _run_one(mode: str, key: str) -> dict:
    """Execute one question under one mode, in its own process."""
    OUT.mkdir(parents=True, exist_ok=True)
    trace = OUT / f"{mode}__{key}.jsonl"
    answer = OUT / f"{mode}__{key}.answer.txt"
    env = {
        **os.environ,
        # A `_fat` suffix runs the same mode with the report schema unslimmed,
        # so the trimmed schema can be A/B'd against the one it replaced.
        "CS_REPORT_MODE": mode.removesuffix("_fat"),
        "CS_REPORT_SLIM": "0" if mode.endswith("_fat") else "1",
        "CS_LOG_FILE": str(trace),
        "CS_LOG_TO_SCREEN": "false",
        "CS_BACKEND": os.getenv("CS_BENCH_BACKEND", "sqlite"),
        # qwen3.8, not qwen3.6: every reference profile in logs/ was made on it,
        # and the two differ by 3x in decode on the same box (36 vs 12.7 tok/s).
        # That gap is not incidental here — `derived` and `raw` win by turning
        # decode into prefill, so the slower model inflates their advantage by
        # roughly 4.5x and would rank the modes on an artefact.
        "CS_MODELS": os.getenv("CS_BENCH_MODELS", "all:ollama_qwen_3_8_27b"),
        "PYTHONPATH": ".",
        # Hand the VRAM back when the run ends. endpoints.yaml pins these models
        # forever, which is right for a server and wrong for a benchmark sharing
        # a box with somebody's testing.
        "CS_KEEP_ALIVE": os.getenv("CS_BENCH_KEEP_ALIVE", "300"),
    }
    script = (
        "import json,sys\n"
        "from dotenv import load_dotenv; load_dotenv()\n"
        "from cs_agent.run import run_question\n"
        "result = run_question(sys.argv[1], on_clarify=lambda payload: 'No preference.')\n"
        "sys.stdout.write(json.dumps({'draft': result.get('draft') or ''}))\n"
    )
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script, QUESTIONS[key]],
            env=env,
            capture_output=True,
            text=True,
            timeout=CELL_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        # One slow cell must not cost the other nineteen. The trace is left on
        # disk so the cell can be diagnosed, and the partial answer file records
        # that it never finished rather than looking merely empty.
        wall = time.time() - started
        answer.write_text(
            f"(timed out after {CELL_TIMEOUT}s — cell did not finish)", encoding="utf-8"
        )
        return {
            "mode": mode,
            "question": key,
            "wall": wall,
            "ok": False,
            "error": f"timed out after {CELL_TIMEOUT}s",
        }
    wall = time.time() - started
    draft = ""
    if proc.returncode == 0:
        try:
            draft = json.loads(proc.stdout.strip().splitlines()[-1]).get("draft", "")
        except (json.JSONDecodeError, IndexError):
            draft = ""
    answer.write_text(draft or f"(no answer)\n\n{proc.stderr[-4000:]}", encoding="utf-8")
    return {
        "mode": mode,
        "question": key,
        "wall": wall,
        "ok": proc.returncode == 0 and bool(draft),
        "error": "" if proc.returncode == 0 else proc.stderr.strip()[-400:],
    }


def _measure(trace: Path) -> dict:
    """Read a finished run's trace for the numbers the comparison turns on.

    The stage of a model call is decided at `llm.start`, where the prompt is,
    and the cost of it arrives at `llm.end`; the two are paired on the callback
    run id the way `latency_profile` does it. A derived or raw run has no report
    call at all, so its report columns come out as zeros — which is the point.
    """
    stats = {
        "report_s": 0.0,
        "report_out": 0,
        "report_calls": 0,
        "total_out": 0,
        "total_in": 0,
        "tool_calls": 0,
        "gate_fails": 0,
        "report_chars": 0,
        "wall_s": 0.0,
    }
    if not trace.exists():
        return stats
    stamps = []
    open_llm: dict[str, str] = {}
    for line in trace.open(encoding="utf-8"):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if timestamp := record.get("timestamp"):
            try:
                stamps.append(_parse_ts(timestamp))
            except ValueError:
                pass
        event = record.get("event")
        run_id = str(record.get("callback_run_id"))
        if event == "tool.start":
            stats["tool_calls"] += 1
        elif event == "llm.start":
            open_llm[run_id] = _stage_of(record.get("messages"))
        elif event == "llm.end":
            stage = open_llm.pop(run_id, "?")
            found: list[dict] = []
            _find_ollama_meta(record.get("response"), found)
            if not found:
                continue
            meta = found[0]
            out = meta.get("eval_count") or 0
            stats["total_out"] += out
            stats["total_in"] += meta.get("prompt_eval_count") or 0
            if stage == "specialist report":
                stats["report_s"] += (meta.get("total_duration") or 0) / 1e9
                stats["report_out"] += out
                stats["report_calls"] += 1
        elif event == "state.update":
            update = record.get("update") or {}
            if record.get("node") == "specialist":
                for report in (update.get("reports") or {}).values():
                    stats["report_chars"] += len(json.dumps(report, default=str))
            elif record.get("node") == "gate":
                stats["gate_fails"] += len(
                    (update.get("gate_result") or {}).get("failures") or []
                )
    if stamps:
        stats["wall_s"] = (max(stamps) - min(stamps)).total_seconds()
    return stats


def _aggregate(modes: list[str], keys: list[str]) -> str:
    rows = []
    for key in keys:
        for mode in modes:
            trace = OUT / f"{mode}__{key}.jsonl"
            answer = OUT / f"{mode}__{key}.answer.txt"
            if not trace.exists():
                continue
            stats = _measure(trace)
            decode, prefill = _rates(trace)
            stats.update(
                mode=mode,
                question=key,
                decode=decode,
                prefill=prefill,
                answer_chars=len(answer.read_text(encoding="utf-8")) if answer.exists() else 0,
            )
            rows.append(stats)
    # The decode column is not decoration: a row whose cells disagree on it was
    # not measuring the same machine, and its comparison has to be thrown away.
    # Compared within a question, never across the table — different questions
    # decode different amounts at different prompt lengths, so a global baseline
    # flags the slowest question rather than the contended cell.
    fastest: dict[str, float] = {}
    for row in rows:
        fastest[row["question"]] = max(fastest.get(row["question"], 0.0), row["decode"])
    lines = [
        "| question | mode | wall s | report s | report % | report tok | report chars "
        "| total out tok | tools | gate fails | answer chars | decode tok/s | prefill tok/s |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    contaminated = []
    for row in rows:
        share = 100 * row["report_s"] / row["wall_s"] if row["wall_s"] else 0
        baseline = fastest.get(row["question"], 0.0)
        drifted = baseline and row["decode"] < baseline * (1 - DRIFT)
        suspect = " ⚠" if drifted else ""
        if drifted:
            contaminated.append(f"{row['question']}/{row['mode']}")
        lines.append(
            f"| {row['question']} | {row['mode']} | {row['wall_s']:.1f} | "
            f"{row['report_s']:.1f} | {share:.0f}% | {row['report_out']:,} | "
            f"{row['report_chars']:,} | {row['total_out']:,} | {row['tool_calls']} | "
            f"{row['gate_fails']} | {row['answer_chars']:,} | "
            f"{row['decode']:.1f}{suspect} | {row['prefill']:,.0f} |"
        )
    if contaminated:
        lines += [
            "",
            f"**⚠ {len(contaminated)} cell(s) ran more than {DRIFT:.0%} below the "
            f"fastest decode rate in this table: {', '.join(contaminated)}.** The "
            "modes differ in how much of their work is decode rather than prefill, "
            "so a degraded cell is not merely slow — it is slow in a way that "
            "changes the ranking. Re-run these before drawing a conclusion.",
        ]
    by_mode: dict[str, list[dict]] = {}
    for row in rows:
        by_mode.setdefault(row["mode"], []).append(row)
    lines += ["", "| mode | runs | mean wall s | mean report s | mean out tok | mean answer chars |", "|---|---|---|---|---|---|"]
    for mode in modes:
        group = by_mode.get(mode) or []
        if not group:
            continue
        n = len(group)
        lines.append(
            f"| {mode} | {n} | {sum(r['wall_s'] for r in group) / n:.1f} | "
            f"{sum(r['report_s'] for r in group) / n:.1f} | "
            f"{sum(r['total_out'] for r in group) / n:,.0f} | "
            f"{sum(r['answer_chars'] for r in group) / n:,.0f} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modes", default=",".join(MODES))
    parser.add_argument("--questions", default=",".join(QUESTIONS))
    parser.add_argument("--report", action="store_true", help="aggregate only")
    parser.add_argument(
        "--resume", action="store_true", help="skip cells that already have a trace"
    )
    parser.add_argument(
        "--force", action="store_true", help="run even with another model in VRAM"
    )
    args = parser.parse_args()
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    keys = [q.strip() for q in args.questions.split(",") if q.strip() in QUESTIONS]

    if not args.report:
        if not args.force:
            _preflight(os.getenv("CS_BENCH_MODEL_NAME", "qwen3.8"))
        for key in keys:
            for mode in modes:
                answer_file = OUT / f"{mode}__{key}.answer.txt"
                done = answer_file.exists() and not answer_file.read_text(
                    encoding="utf-8"
                ).startswith(("(timed out", "(no answer"))
                if args.resume and done:
                    print(f"· {mode:8} {key}  (already done)", flush=True)
                    continue
                print(f"→ {mode:8} {key}", flush=True)
                outcome = _run_one(mode, key)
                mark = "ok" if outcome["ok"] else f"FAILED {outcome['error'][:200]}"
                print(f"  {outcome['wall']:6.1f}s  {mark}", flush=True)

    table = _aggregate(modes, keys)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.md").write_text(table + "\n", encoding="utf-8")
    print("\n" + table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
