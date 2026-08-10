"""Interactive CLI entry point for the C&S product agent."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from cs_agent.graph import build_graph


def _initial_state(question: str) -> dict[str, Any]:
    return {
        "messages": [HumanMessage(content=question)],
        "plan": None,
        "evidence": [],
        "clarify_count": 0,
        "tool_calls_made": 0,
        "assumptions": [],
        "draft": None,
        "validation": None,
    }


def _answer_interrupt(payload: Any) -> str:
    questions = payload.get("questions", []) if isinstance(payload, dict) else [payload]
    print("\nI need a little more information:")
    for index, question in enumerate(questions, 1):
        print(f"  {index}. {question}")
    return input("Answer: ").strip()


def run_question(question: str) -> dict[str, Any]:
    graph = build_graph(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = graph.invoke(_initial_state(question), config=config)
    while result.get("__interrupt__"):
        interrupt_record = result["__interrupt__"][0]
        payload = getattr(interrupt_record, "value", interrupt_record)
        result = graph.invoke(
            Command(resume=_answer_interrupt(payload)),
            config=config,
        )
    return result


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="C&S product support agent")
    parser.add_argument("--question", help="Run one question instead of prompting first")
    args = parser.parse_args()
    question = args.question or input("Product question: ").strip()
    if not question:
        parser.error("a product question is required")
    try:
        result = run_question(question)
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.", file=sys.stderr)
        return 130

    print("\nAnswer\n------")
    print(result.get("draft") or "No answer was produced.")
    print("\nValidation\n----------")
    print(json.dumps(result.get("validation"), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
