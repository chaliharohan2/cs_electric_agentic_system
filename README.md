# CS Electric Client Support Agent

Multi-agent CLI product-support system over a read-only SQLite catalogue artifact
built from `cs_electric_v2` Postgres `mv_*` views. Synthetic fixtures remain for
offline unit tests.

For a full walkthrough of the catalogue model, graph, tools, and analytics, see
[`ARCHITECTURE.md`](ARCHITECTURE.md). The SQLite file layout, columns, and
current build counts are in [`SQLITE-CATALOG.md`](SQLITE-CATALOG.md).
Migration notes:
[`product-agent-plan-v2-sqlite-db-plan.md`](product-agent-plan-v2-sqlite-db-plan.md).

## Setup

```bash
source /home/rohan/Nyalazone/cs_electric_agent/venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `ANTHROPIC_API_KEY` (and optionally `LOCAL_LLM_API_KEY`) in `.env`. Configure:

```bash
CS_BACKEND=sqlite
CS_SQLITE_PATH=artifacts/catalog-latest.sqlite
CS_CHECKPOINT_PATH=state/checkpoints.sqlite
DATABASE_URL=postgresql://postgres:your-password@localhost:5432/cs_electric_v2
CS_EMBEDDING_MODEL=gte_base_en_v1_5
```

Keep database credentials in `.env`; do not commit them.

## Build the SQLite catalogue

Postgres remains the **build source**. Refresh materialized views, then build:

```bash
python -m cs_agent.db.refresh setup   # first time
python -m cs_agent.db.refresh refresh # after product_chunks reloads
python scripts/build_sqlite.py
```

This writes `artifacts/catalog-<date>.sqlite`, `artifacts/catalog-latest.sqlite`,
and `artifacts/build_report.json` (factless SKUs, composites, price mismatches).

## Run

```bash
CS_BACKEND=sqlite python -m cs_agent.run
# or
python -m cs_agent.run --question "Compare two WiNmaster 3 ACB SKUs."
# reuse a persisted conversation (SqliteSaver)
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
The SQLite build stores corpus embeddings as BLOBs; `search_documents` uses
sqlite-vec scalar cosine distance over a pre-filtered candidate set. If
`sqlite-vec` cannot load, or embeddings are absent, FTS5 lexical search is
used (`mode: "lexical"`).

## Workflow

`intake` resolves follow-ups, the planner dispatches one to five private specialists
in parallel, a deterministic gate checks each report, and the composer performs a
structured sufficiency pass before writing the answer. Missing evidence triggers only
the named specialist, up to the configured revision cap. Runtime caps live in
`cs_agent/config/limits.yaml` and can be overridden with `CS_GLOBAL_TOOL_BUDGET`,
`CS_PER_AGENT_TOOL_BUDGET`, `CS_COMPOSER_REVISIONS`, and related variables.

## Execution tracing

Every run appends structured JSONL events to `logs/cs_agent_trace.jsonl`.
Configure tracing in `.env`:

```bash
CS_LOG_FILE=logs/cs_agent_trace.jsonl
CS_LOG_TO_SCREEN=true
```

## Tests

```bash
python -m unittest tests.test_framework tests.test_sqlite
```

Vector integration tests are intentionally excluded. After 768-dimensional corpus
vectors are loaded, run them explicitly with:

```bash
CS_VECTOR_TEST_FAMILY="..." make test-vector
```
