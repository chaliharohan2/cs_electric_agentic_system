# CS Electric Client Support Agent

CLI-only LangGraph product-support framework backed by synthetic WiNbreak2 and
DP-Contactor fixture data.

## Setup

```bash
source /home/rohan/Nyalazone/cs_electric_agent/venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `ANTHROPIC_API_KEY` (and optionally `LOCAL_LLM_API_KEY`) in `.env`.

## Run

```bash
python -m cs_agent.run
# or
python -m cs_agent.run --question "What is the Icu of WIN2-250 at 415 V?"
```

Model routing is controlled by `cs_agent/config/endpoints.yaml`. Override with
`CS_MODELS=all:qwen_27b` or `CS_MODELS=agent:qwen_a3b,composer:qwen_27b`.
`CS_BACKEND` defaults to `fixtures`; `postgres` raises `SCHEMA_PENDING`.

## Execution tracing

Every run appends structured JSONL events to `logs/cs_agent_trace.jsonl`.
The trace includes run lifecycle, node entry/exit and transitions, state snapshots
and updates, LLM requests/responses, tool calls/results, interrupts, and errors.
Events are also printed to the terminal by default.

Configure tracing in `.env`:

```bash
CS_LOG_FILE=logs/cs_agent_trace.jsonl
CS_LOG_TO_SCREEN=true
```

Set `CS_LOG_TO_SCREEN=false` to keep file logging while suppressing trace output
in the terminal.

## Tests

```bash
python -m unittest tests.test_framework
```
