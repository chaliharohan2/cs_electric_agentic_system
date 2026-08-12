# CS Electric Client Support Agent

CLI LangGraph product-support agent backed by PostgreSQL `in_use.product_chunks`,
with synthetic fixtures retained for offline tests.

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
DATABASE_URL=postgresql://postgres:your-password@localhost:5432/cs_electric
CS_EMBEDDING_MODEL=minilm_l6_v2
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
```

Model routing is controlled by `cs_agent/config/endpoints.yaml`. Override with
`CS_MODELS=all:qwen_27b` or `CS_MODELS=agent:qwen_a3b,composer:qwen_27b`.
Set `CS_BACKEND=fixtures` for deterministic offline fixture tests.

## Embeddings

Query embedding profiles live in `cs_agent/config/embeddings.yaml`. The current
`minilm_l6_v2` profile uses `sentence-transformers/all-MiniLM-L6-v2` and emits the
384 dimensions stored in `product_chunks.embedding`.

The prepared `gte_base_en_v1_5` profile emits 768 dimensions. Do not enable it until
the catalogue has been re-embedded, the vector column has been migrated to
`vector(768)`, and the vector index has been rebuilt. Runtime dimension validation
fails clearly instead of issuing an invalid similarity query.

## Execution tracing

Every run appends structured JSONL events to `logs/cs_agent_trace.jsonl`.
The trace includes run lifecycle, node entry/exit and transitions, state snapshots
and updates, LLM requests/responses, tool calls/results, interrupts, and errors.
The JSONL file retains all details. Terminal output is intentionally concise: graph
transitions, summarized state changes, tool inputs, identifying result fields/counts,
clarification pauses, validation status, and errors.

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
