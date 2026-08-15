"""Interactive CLI entry point for the C&S product agent."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from cs_agent.config.limits import get_limits
from cs_agent.graph import build_graph
from cs_agent.observability import AgentCallbackHandler, TraceLogger


@contextmanager
def _checkpointer():
    backend = os.getenv("CS_BACKEND", "sqlite").lower()
    if backend == "fixtures":
        yield MemorySaver()
        return
    if backend == "sqlite":
        limits = get_limits()
        checkpoint_path = os.getenv("CS_CHECKPOINT_PATH") or limits.checkpoint_path
        path = Path(checkpoint_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with SqliteSaver.from_conn_string(str(path)) as saver:
            saver.setup()
            yield saver
        return
    raise ValueError("CS_BACKEND must be 'sqlite' or 'fixtures'")


def _initial_state(
    question: str, session: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "messages": [HumanMessage(content=question)],
        "session": session or {
            "turns": [],
            "focus_skus": [],
            "focus_family": None,
            "resolved_params": {},
            "prior_reports": {},
        },
        "standalone_question": question,
        "plan": None,
        "dispatch": [],
        "reports": {"__reset__": {}},
        "evidence": [],
        "clarify_count": 0,
        "tool_calls_made": 0,
        "turn_tool_calls_start": 0,
        "tool_failures": 0,
        "revision_round": 0,
        "gate_retries": 0,
        "gate_result": None,
        "sufficiency": None,
        "assumptions": [],
        "draft": None,
    }


def _answer_interrupt(payload: Any) -> str:
    questions = payload.get("questions", []) if isinstance(payload, dict) else [payload]
    print("\nI need a little more information:")
    for index, question in enumerate(questions, 1):
        print(f"  {index}. {question}")
    return input("Answer: ").strip()


def run_question(
    question: str,
    *,
    trace: TraceLogger | None = None,
    thread_id: str | None = None,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    owns_trace = trace is None
    trace = trace or TraceLogger()
    callback = AgentCallbackHandler(trace)
    thread_id = thread_id or str(uuid.uuid4())
    initial_state = _initial_state(question, session=session)
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [callback],
        "metadata": {"trace_run_id": trace.run_id},
    }
    trace.event(
        "run.start",
        thread_id=thread_id,
        question=question,
        log_file=str(trace.file_path),
        print_to_screen=trace.print_to_screen,
    )
    trace.event(
        "state.initialized",
        state=initial_state,
    )
    trace.event(
        "node.transition",
        from_node="START",
        to_node="intake",
        transition_type="fixed",
    )
    trace.event("agent.change", from_agent="START", to_agent="intake")
    try:
        with _checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer, trace=trace)
            result = graph.invoke(initial_state, config=config)
            while result.get("__interrupt__"):
                interrupt_record = result["__interrupt__"][0]
                payload = getattr(interrupt_record, "value", interrupt_record)
                trace.event("run.interrupt", payload=payload)
                answer = _answer_interrupt(payload)
                trace.event("run.resume", answer=answer)
                result = graph.invoke(
                    Command(resume=answer),
                    config=config,
                )
        trace.event("run.end", status="completed", final_state=result)
        return result
    except BaseException as exc:
        trace.event("run.end", status="error", error=exc)
        raise
    finally:
        if owns_trace:
            trace.close()


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="C&S product support agent")
    parser.add_argument("--question", help="Run one question instead of prompting first")
    parser.add_argument("--thread-id", help="Stable conversation thread identifier")
    args = parser.parse_args()
    question = args.question or input("Product question: ").strip()
    if not question:
        parser.error("a product question is required")
    try:
        thread_id = args.thread_id or str(uuid.uuid4())
        session = None
        result = run_question(question, thread_id=thread_id, session=session)
        if not args.question:
            print("\nAnswer\n------")
            print(result.get("draft") or "No answer was produced.")
            while True:
                follow_up = input("\nFollow-up (blank to finish): ").strip()
                if not follow_up:
                    break
                session = result.get("session")
                result = run_question(
                    follow_up, thread_id=thread_id, session=session
                )
                print("\nAnswer\n------")
                print(result.get("draft") or "No answer was produced.")
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.", file=sys.stderr)
        return 130

    if args.question:
        print("\nAnswer\n------")
        print(result.get("draft") or "No answer was produced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
