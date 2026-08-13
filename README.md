# CS Electric Client Support Agent

Multi-agent CLI product-support system backed by the `cs_electric_v2` PostgreSQL
catalogue, with synthetic fixtures retained for offline tests.

For a full walkthrough of the catalogue model, materialized views, main graph,
every node, and the analytics sub-agent, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Setup

```bash
source /home/rohan/Nyalazone/cs_electric_agent/venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `ANTHROPIC_API_KEY` (and optionally `LOCAL_LLM_API_KEY`) in `.env`. Configure:

```bash
CS_BACKEND=postgres
DATABASE_URL=postgresql://postgres:your-password@localhost:5432/cs_electric_v2
CS_EMBEDDING_MODEL=gte_base_en_v1_5
```

Keep database credentials in `.env`; do not commit them.

## Database setup

Create the derived catalogue views after the initial load:

```bash
python -m cs_agent.db.refresh setup
python -m cs_agent.db.refresh inspect
# equivalent: make setup-db && make inspect
```

After each wholesale reload of `in_use.product_chunks`, refresh in dependency order:

```bash
python -m cs_agent.db.refresh refresh
# equivalent: make refresh
```

## Run

```bash
python -m cs_agent.run
# or
python -m cs_agent.run --question "Compare two WiNmaster 3 ACB SKUs."
# reuse a persisted conversation
python -m cs_agent.run --thread-id customer-42
```

Model routing is controlled by `cs_agent/config/endpoints.yaml`. Override with
`CS_MODELS=all:qwen_27b` or `CS_MODELS=agent:qwen_a3b,composer:qwen_27b`.
A profile's `provider` picks the client: `openai` for Anthropic and vLLM,
`ollama` for a native Ollama server (`ollama_27b`, `ollama_35b`).
Set `CS_BACKEND=fixtures` for deterministic offline fixture tests.

## Embeddings

The active `gte_base_en_v1_5` profile uses
`Alibaba-NLP/gte-base-en-v1.5` and emits normalized 768-dimensional query vectors.
Database setup migrates an empty embedding column to `vector(768)`. Corpus ingestion
is external to this repository. Until vectors are loaded, `search_documents` uses its
PostgreSQL full-text fallback and returns `mode: "lexical"`.

## Workflow

`intake` resolves follow-ups, the planner dispatches one to five private specialists
in parallel, a deterministic gate checks each report, and the composer performs a
structured sufficiency pass before writing the answer. Missing evidence triggers only
the named specialist, up to the configured revision cap. Runtime caps live in
`cs_agent/config/limits.yaml` and can be overridden with `CS_GLOBAL_TOOL_BUDGET`,
`CS_PER_AGENT_TOOL_BUDGET`, `CS_COMPOSER_REVISIONS`, and related variables.

## Execution tracing

Every run appends structured JSONL events to `logs/cs_agent_trace.jsonl`.
The trace includes run lifecycle, node entry/exit and transitions, state snapshots
and updates, LLM requests/responses, tool calls/results, interrupts, and errors.
The JSONL file retains all details. Terminal output is intentionally concise: graph
transitions, summarized state changes, tool inputs, identifying result fields/counts,
clarification pauses, and errors.

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

Vector integration tests are intentionally excluded. After 768-dimensional corpus
vectors are loaded, run them explicitly with:

```bash
CS_VECTOR_TEST_FAMILY="..." make test-vector
```
