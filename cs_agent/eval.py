"""Small JSONL evaluation harness for v2 agent and endpoint profiles."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from cs_agent.llm.factory import resolve_endpoint
from cs_agent.run import run_question


class EvalCase(BaseModel):
    question: str
    expected_agents: list[str] = Field(default_factory=list)
    expected_skus: list[str] = Field(default_factory=list)


def evaluate(cases: list[EvalCase]) -> dict[str, Any]:
    details = []
    per_agent: dict[str, dict[str, int]] = defaultdict(
        lambda: {"expected": 0, "dispatched": 0, "correct": 0}
    )
    started = time.monotonic()
    for case in cases:
        before = time.monotonic()
        result = run_question(case.question)
        actual_agents = set(result.get("reports", {}))
        expected_agents = set(case.expected_agents)
        answer = result.get("draft") or ""
        for agent in expected_agents | actual_agents:
            per_agent[agent]["expected"] += int(agent in expected_agents)
            per_agent[agent]["dispatched"] += int(agent in actual_agents)
            per_agent[agent]["correct"] += int(
                agent in expected_agents and agent in actual_agents
            )
        details.append({
            "question": case.question,
            "expected_agents": sorted(expected_agents),
            "actual_agents": sorted(actual_agents),
            "agent_exact_match": expected_agents == actual_agents,
            "expected_sku_recall": (
                sum(code in answer for code in case.expected_skus)
                / max(1, len(case.expected_skus))
            ),
            "tool_calls": result.get("tool_calls_made", 0),
            "elapsed_seconds": time.monotonic() - before,
        })
    endpoint_profile = {
        node: resolve_endpoint(node).model
        for node in ("intake", "planner", "agent", "composer")
    }
    return {
        "cases": len(cases),
        "elapsed_seconds": time.monotonic() - started,
        "agent_exact_match_rate": (
            sum(item["agent_exact_match"] for item in details) / max(1, len(details))
        ),
        "per_agent": dict(per_agent),
        "endpoint_profile": endpoint_profile,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path, help="JSONL EvalCase input")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = [
        EvalCase.model_validate_json(line)
        for line in args.cases.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rendered = json.dumps(evaluate(cases), indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
