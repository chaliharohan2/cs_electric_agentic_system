# C&S Product Agent — Architecture Guide

This document explains the repository from first principles: what the agent does, how data is stored, how the LangGraph workflow runs, what every node is for, and how the analytics sub-agent fits in.

If you are new to the project, start here.

---

## 1. What this project is

C&S Electric sells electrical products (air circuit breakers, MCCBs, contactors, switches, and many more). Product information lives in a PostgreSQL table of brochure/pricelist **chunks** — pieces of text plus structured JSON facts and vector embeddings.

This repo is a **CLI product-support agent** that answers questions over that catalogue:

- lookup facts about a specific ordering code (SKU)
- compare a few named SKUs
- select / shortlist products by rating, poles, breaking capacity, etc.
- explain qualitative brochure content
- run free-form analytics across many SKUs

**Stack:** Python 3.11+, LangChain, LangGraph, PostgreSQL 17 + pgvector, OpenAI-compatible LLM endpoints.

**Entry point:**

```bash
python -m cs_agent.run --question "Which WiNmaster 3 ACB is rated 630 A with 3 poles?"
```

---

## 2. Mental model of the catalogue

Think of the catalogue as a tree:

```
Category  (e.g. "ACB – WiNmaster 3")
  └── Family  (often same name as category today)
        └── SKU  (ordering code, e.g. WX306L3P1MDOA(S))
              ├── facts / specifications
              ├── decoded ordering-code axes
              └── brochure text chunks + embeddings
```

Important identifiers:

| Concept | Meaning |
|---------|---------|
| `sku_code` | Ordering code. **This is the only product ID the agent talks about.** |
| `product_id` | Internal database key. Kept in views for joins; never returned to the agent. |
| `spec_id` | Exact specification key, e.g. `rated_current_a`, `breaking_capacity_ka`, `price_inr`. |
| `value_kind` | How a fact should be read: `scalar`, `range`, `set`, or `text`. |

A SKU’s ordering code also **decodes** into axes such as rating, poles, breaking capacity, frame, release/trip unit, and mounting. Those axes power browsing and facet filters.

---

## 3. Source data and why we use materialized views

### 3.1 Source table: `in_use.product_chunks`

The live source of truth is one denormalised table. Each row is roughly:

- a chunk of brochure/pricelist text (`content`)
- a vector embedding (`embedding vector(384)`)
- JSON blobs that repeat per SKU: `taxonomy`, `product`, `details`
- flags like `is_active`, `chunk_type`

One physical product (SKU) typically has several chunks. The same `product` / `taxonomy` / `details` JSON is repeated across those chunks. Querying that table directly for every tool would mean:

1. constantly de-duplicating SKUs
2. digging into nested JSON for every filter
3. fighting the fact that the GIN JSON index is for containment, not numeric ranges

So the agent **does not** query `product_chunks` for structured lookup. It reads **materialized views** derived from it. Vector search still uses `product_chunks.embedding`.

### 3.2 Helper: `in_use.safe_num(text)`

Ingestion is not perfectly clean. Some “numeric” fields contain non-numeric text. PostgreSQL’s typed JSON extraction would abort a whole query on one bad value.

`safe_num` converts a string to a `double precision` only when it looks like a plain number; otherwise it returns `NULL`:

```sql
CREATE OR REPLACE FUNCTION in_use.safe_num(t text) RETURNS double precision
LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN t ~ '^-?[0-9]+(\.[0-9]+)?$' THEN t::double precision END
$$;
```

### 3.3 The four materialized views

Defined in [`cs_agent/db/views.sql`](cs_agent/db/views.sql). Created / refreshed via:

```bash
python -m cs_agent.db.refresh setup    # create helper + views + indexes
python -m cs_agent.db.refresh refresh  # after a wholesale data reload
python -m cs_agent.db.refresh inspect  # print row counts + embedding dimension
# or: make setup-db / make refresh / make inspect
```

Refresh order matters because later views depend on earlier ones:

`mv_sku` → `mv_fact` → `mv_spec_registry` and `mv_facet`

#### `in_use.mv_sku` — one row per SKU

Built with `DISTINCT ON (product_id)` from active chunks.

Columns include:

- `sku_code`, `family`, `category`, `url`
- `decoded` — ordering-code axes as JSON
- `completeness`, `sources`
- `has_price`, `fact_count`

Unique indexes on `product_id` and `sku_code`.

#### `in_use.mv_fact` — one row per (SKU, specification)

Joins each SKU to the facts array from **one representative chunk** (lowest chunk `id` for that product), then unnests `details.facts`.

Columns include:

- `spec_id`, `spec_label`, `unit`
- `value_num`, `value_min`, `value_max`, `value_display`, `value_kind`
- `source_of_truth` (`pricelist_table` vs `code_grammar`)
- `derived`, `fact_sentence`

**Range semantics used by search / analytics:**

| Operator | Predicate |
|----------|-----------|
| `gte x` | `COALESCE(value_max, value_num) >= x` |
| `lte x` | `COALESCE(value_min, value_num) <= x` |
| `eq x` | `x BETWEEN COALESCE(value_min, value_num) AND COALESCE(value_max, value_num)` |
| `contains s` | `value_display ILIKE '%s%'` |

Using `value_num` alone would silently drop every range-valued fact.

#### `in_use.mv_spec_registry` — vocabulary of specs per category

Grouped from `mv_fact`. Tells the agent which `spec_id`s exist, with units, value kinds, SKU counts, and observed min/max. The agent is expected to call this **before inventing filter IDs**.

#### `in_use.mv_facet` — ordering-code axes with counts

Expands `mv_sku.decoded` with `jsonb_each`. Non-object `decoded` values are treated as empty objects so the view still builds cleanly.

Axes look like `rating_idx`, `poles`, `breaking`, `frame`, `release`, `mounting`, `acb_type`, `std_accessories`.

### 3.4 Approximate live sizes (after setup)

On the loaded database these were observed around:

| Object | Approx. rows |
|--------|--------------|
| `product_chunks` (active) | ~99k |
| `mv_sku` | ~4.4k |
| `mv_fact` | ~19.8k |
| `mv_spec_registry` | ~262 |
| `mv_facet` | ~1.4k |
| embedding type | `vector(384)` |

---

## 4. High-level architecture

```
User question (CLI)
        │
        ▼
┌───────────────────┐
│  cs_agent.run     │  loads .env, builds graph, handles clarify interrupts
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐     tools call      ┌──────────────────────────┐
│  Main LangGraph   │ ──────────────────► │ CatalogBackend           │
│  (planner→…→END)  │                     │  fixtures | postgres     │
└─────────┬─────────┘                     └────────────┬─────────────┘
          │                                            │
          │ analytics_query tool                       ▼
          │                               ┌──────────────────────────┐
          └─────────────────────────────► │ Analytics subgraph       │
                                          │ analyst⇄SQL tool→summary │
                                          └──────────────────────────┘
```

Key packages under `cs_agent/`:

| Path | Role |
|------|------|
| `graph/` | Main agent state machine |
| `graph/nodes/` | Individual node implementations |
| `tools/` | Tool schemas, descriptions, wrappers, registry |
| `backends/` | Data access: fixtures (tests) or Postgres (production) |
| `subgraphs/analytics/` | SQL analytics sub-agent exposed as one tool |
| `db/` | Materialized view SQL + refresh CLI |
| `llm/` | Model factory + structured JSON helper |
| `embeddings/` | Configurable query embedding factory |
| `prompts/` | Markdown system prompts per node |
| `validation/` | Deterministic numeric fidelity checks |
| `config/` | LLM endpoints + embedding profiles |
| `run.py` | CLI |

`CS_BACKEND=postgres` is the real path. `CS_BACKEND=fixtures` keeps offline unit tests deterministic with synthetic JSON data.

---

## 5. Shared state (`AgentState`)

Every node reads/writes a shared state object:

```python
messages          # conversation + tool calls/results
plan              # planner output (intent, categories, target_specs, …)
evidence          # append-only list of retrieved facts the answer may cite
clarify_count     # how many clarify rounds happened (hard cap 2)
tool_calls_made   # how many tools have completed (hard cap 12)
assumptions       # defaults taken when the user did not answer
draft             # composer’s current answer text
validation        # validator result / metrics
```

**Evidence** is the only thing the validator trusts. Each evidence record looks like:

```python
tool, sku_code, spec_id,
value_num, value_min, value_max, value_display, value_kind,
unit, source_of_truth, text
```

`messages` uses LangGraph’s `add_messages` reducer (append/merge). `evidence` uses `operator.add` (append-only).

---

## 6. Main graph flow

Built in [`cs_agent/graph/build.py`](cs_agent/graph/build.py).

```text
START
  │
  ▼
planner
  │
  ├── needs_clarification AND clarify_count < 2 ──► clarify ──► planner
  │
  └── otherwise ──► agent
                      │
                      ├── wants tools AND budget allows ──► tools
                      │                                       │
                      │                                       ▼
                      │                               record_evidence
                      │                                       │
                      │                                       ▼
                      │                                     agent   (loop)
                      │
                      └── no more tools / budget hit ──► composer
                                                           │
                                                           ▼
                                                       validator
                                                           │
                                                           ├── fail, attempt < 2 ──► composer
                                                           └── otherwise ──► END
```

Hard caps are enforced in **graph edges**, not only in prompts:

- clarify rounds: max **2**
- completed tool calls: max **12** (a parallel batch that would exceed 12 is not dispatched)

Persistence:

- Postgres backend runs use `PostgresSaver` (needed for `interrupt()` / clarify resume)
- fixture / test runs use `MemorySaver`

---

## 7. Each main-graph node, explained

### 7.1 `planner`

**File:** `cs_agent/graph/nodes/planner.py`  
**Prompt:** `cs_agent/prompts/planner.md`  
**LLM role:** plan the approach; does **not** call tools

The planner reads the user’s question and returns structured JSON (`Plan`):

- `intent`: `lookup` | `compare` | `select` | `explain`
- `categories`: catalogue areas in scope (may be empty)
- `target_specs`: specs likely needed, in plain words
- `known_params` / `open_params`
- `needs_clarification`: true only if a missing parameter would change **which SKU/family** is recommended
- `strategy`: short prose plan for the agent

If clarify has already hit the cap and the planner still wants clarification, remaining open parameters become **assumptions** and the run continues.

**Next:** `clarify` or `agent`.

### 7.2 `clarify`

**File:** `cs_agent/graph/nodes/clarify.py`  
**Prompt:** `cs_agent/prompts/clarify.md`

When the plan is underspecified, this node asks up to **3** short questions (with suggested defaults), then pauses the graph with LangGraph `interrupt()`.

The CLI (`run.py`) prints the questions, waits for the user’s answer, and resumes with `Command(resume=...)`. The answer is appended as a human message and `clarify_count` increments. Control returns to **planner**, which can revise the plan with the new information.

### 7.3 `agent`

**File:** `cs_agent/graph/nodes/agent.py`  
**Prompt:** `cs_agent/prompts/agent.md`

This is the tool-using reasoner. It receives:

- the conversation so far
- the current plan
- remaining tool budget

It calls `get_model("agent").bind_tools(TOOLS)` and either:

1. emits one or more **tool calls**, or
2. stops calling tools (enough evidence gathered)

It does **not** increment `tool_calls_made`. Counting happens only after tools actually finish (`record_evidence`).

**Next:** `tools` or `composer`.

### 7.4 `tools`

Stock LangGraph `ToolNode(TOOLS)`.

Executes whatever tool calls the agent requested (including in parallel), wraps results as `ToolMessage`s, and handles tool errors as messages rather than crashing the graph.

**Next:** always `record_evidence`.

### 7.5 `record_evidence`

**File:** `cs_agent/graph/nodes/record_evidence.py`  
**No LLM** — deterministic Python parsers

Reads the latest `ToolMessage`s and converts them into normalized `Evidence` rows:

| Tool | Evidence produced |
|------|-------------------|
| `product_search`, `get_sku`, `compare_skus` | one record per fact / returned spec |
| `search_documents` | one record per chunk (`text`) |
| `analytics_query` | structured numeric evidence + factual summary/limitations |
| `taxonomy_browse`, `list_canonical_specs` | summary/count payload only (not citable specs) |

Also increments `tool_calls_made` by the number of completed tool messages.

**Next:** always back to `agent` (ReAct-style loop).

### 7.6 `composer`

**File:** `cs_agent/graph/nodes/composer.py`  
**Prompt:** `cs_agent/prompts/composer.md`

Writes the final answer using **only** the evidence table and listed assumptions. Citation style is provenance-based, e.g.:

- `(C&S pricelist)` for `source_of_truth = pricelist_table`
- `(derived from ordering code)` for `code_grammar`

It must report ranges as ranges, treat missing specs as “not published”, and treat POR prices as price-on-request (not zero).

If the validator previously failed, the composer also receives the list of validation errors to correct.

### 7.7 `validator`

**File:** `cs_agent/graph/nodes/validator.py`  
**Logic:** `cs_agent/validation/numeric_fidelity.py`  
**No LLM**

Checks that numbers in the draft are supported by evidence:

1. strip ordering codes and standards first (so `06` inside `WX306…` is not treated as a claim)
2. extract remaining number/unit spans
3. ignore numbers that already appeared in the user’s question, years, ordinals
4. accept a figure if it matches `value_num`, falls in `[value_min, value_max]`, or matches `value_display` for text/set specs

Routing:

- first failure → back to `composer`
- second failure → strip unsupported sentences and append a caveat that some figures could not be verified

Reports `numbers_total / matched / unmatched[]` in the validation payload.

---

## 8. Tools the agent can call

Registered in [`cs_agent/tools/registry.py`](cs_agent/tools/registry.py). All structured tools go through `cs_agent/tools/impl.py` → `CatalogBackend`.

| Tool | Purpose |
|------|---------|
| `taxonomy_browse` | Categories → families → decoded facet axes with SKU counts |
| `list_canonical_specs` | Exact `spec_id`s, units, kinds, observed min/max for a category |
| `product_search` | Primary numeric/facet/code search over SKUs |
| `get_sku` | Full detail for one ordering code (`facts`, `decoded`, optional `content`/`sources`) |
| `compare_skus` | Deterministic side-by-side pivot for 2–10 SKUs (no free-form SQL) |
| `search_documents` | Semantic brochure search (qualitative questions only) |
| `analytics_query` | Bounded multi-query analysis over many SKUs/views (subgraph) |

### Text matching is fuzzy

Every text field a tool filters on — `category`, `family`, `sku_code`, free `text`,
facet axis/value, and `spec_id` — is matched with case-insensitive `ILIKE '%term%'`
rather than exact equality. Exact string matching made exploration fail whenever the
agent guessed a slightly different name (`winmaster 3` vs `ACB – WiNmaster 3`).

Consequences worth knowing:

- `taxonomy_browse("acb")` returns all three ACB families.
- `product_search(category="winmaster 3", filters=[{spec_id: "rated_current", …}])`
  still matches `rated_current_a`.
- `get_sku` resolves a partial/lower-case code, and reports `requested_sku_code` plus
  `other_matches` when the resolved code differs from what was asked.
- `compare_skus` resolves each code and lists anything it could not match under
  `unresolved_sku_codes`.
- Queries are heavier (no index-only equality lookups); this is an accepted trade-off
  for reliable exploration.

Typical sequencing taught by the agent prompt:

1. browse taxonomy / facets  
2. list exact spec IDs  
3. `product_search` to shortlist  
4. `get_sku` or `compare_skus` for detail  
5. `search_documents` only for qualitative “how/why” questions  
6. `analytics_query` for complex quantitative work across many SKUs/views

### Document search notes

On Postgres, `search_documents`:

1. embeds the query with the configured embedding profile
2. validates embedding dimension against `product_chunks.embedding` (currently 384)
3. runs cosine distance (`<=>`) with optional category/family/sku filters
4. **deduplicates identical content** with `md5(content)` so family-level tables are not returned six times

---

## 9. Analytics sub-agent graph

`analytics_query` is **one tool** from the main agent’s point of view, but internally it is its own LangGraph subgraph (`cs_agent/subgraphs/analytics/`).

```text
START
  │
  ▼
prepare             # load spec registry; initialize query count
  │
  ▼
analyst              # tool-bound LLM chooses the next focused SELECT
  │
  ├── tool call, budget remains ──► execute_analytics_sql
  │                                      │
  │                                      ▼
  │                                record_queries
  │                                      │
  │                   budget remains ────┘
  │
  └── complete or cap reached ──► summarize
                                     │
                                     ▼
                                    END
```

### Nodes

| Node | What it does |
|------|--------------|
| `prepare` | Fetches `list_canonical_specs(None)` so the analyst knows legal `spec_id`s |
| `analyst` | Uses a model bound to exactly one private tool. It can decompose the question, issue one focused `SELECT` at a time, inspect results/errors, cross-check, and stop early. |
| `query` | Runs `execute_analytics_sql` through a private `ToolNode`; the main agent cannot call this SQL tool directly. |
| `record_queries` | Counts every execution, including failed SQL, against the hard internal budget. |
| `summarize` | Produces a Pydantic-validated factual report with a concise summary, numeric evidence, query count, limitations, and optional error. It must not infer, recommend, or expose raw SQL/results. |

`AnalyticsReport` fields: `summary`, `evidence`, `queries_run`, `limitations`,
`error`. Each numeric evidence item carries its supporting statement, raw/display
value, and optional unit, SKU, and spec ID so the main numeric-fidelity validator can
still verify the composed answer.

The default hard cap is four SQL executions. Set `CS_ANALYTICS_MAX_QUERIES` to a
positive integer to change it. The router enforces the cap independently of the
prompt. The analytics prompt encodes the same range predicates as the structured
search tools and requires identifying products by `sku_code` only (never
`product_id`).

---

## 10. Models and embeddings (configuration)

### LLMs

[`cs_agent/config/endpoints.yaml`](cs_agent/config/endpoints.yaml) maps each node name to an endpoint profile (`sonnet`, `qwen_a3b`, `qwen_27b`, …).

[`cs_agent/llm/factory.py`](cs_agent/llm/factory.py) builds a `ChatOpenAI` client for that node. Override without editing YAML:

```bash
CS_MODELS=all:qwen_27b
# or
CS_MODELS=agent:qwen_a3b,composer:qwen_27b
```

Structured JSON nodes use `cs_agent/llm/structured.py` (prompt schema + validate-then-retry), because providers differ on strict tool/schema conformance.

### Embeddings

[`cs_agent/config/embeddings.yaml`](cs_agent/config/embeddings.yaml):

| Profile | Model | Dimension |
|---------|-------|-----------|
| `minilm_l6_v2` (active) | `sentence-transformers/all-MiniLM-L6-v2` | 384 |
| `gte_base_en_v1_5` (prepared) | `Alibaba-NLP/gte-base-en-v1.5` | 768 |

Select with `CS_EMBEDDING_MODEL=minilm_l6_v2`.

**Do not switch to the 768-d profile** until the catalogue is re-embedded and the column/index is migrated to `vector(768)`. The factory checks dimensions and fails clearly on mismatch.

---

## 11. Backends

[`cs_agent/backends/protocol.py`](cs_agent/backends/protocol.py) defines the catalogue API.

- **`PostgresBackend`**: production implementation against the materialized views + pgvector.
- **`FixturesBackend`**: synthetic SKU-shaped data for unit tests / offline runs.

Choose with `CS_BACKEND=postgres|fixtures` and `DATABASE_URL=...`.

---

## 12. Observability

Every run can emit structured JSONL events (`logs/cs_agent_trace.jsonl` by default):

- run start/end
- node entry/exit and transitions
- state snapshots/updates
- LLM and tool callbacks
- clarify interrupt / resume
- errors

The JSONL file keeps those complete payloads for debugging. The terminal renderer does
not dump them. It prints only:

- graph transitions (`planner → agent`, etc.)
- concise state changes (plan intent, evidence count, tool budget, validation result)
- tool inputs and summarized outputs (result count plus SKU/spec/category identifiers)
- clarification pauses/resumes, errors, and run completion

Toggle terminal progress output with `CS_LOG_TO_SCREEN`.

---

## 13. End-to-end example (happy path)

Question: *“Find a WiNmaster 3 ACB around 630 A, 3-pole, and show its key specs.”*

1. **planner** → intent `select`, category `ACB – WiNmaster 3`, open params maybe empty.
2. **agent** calls `taxonomy_browse` / `list_canonical_specs`.
3. **tools** run; **record_evidence** stores counts/spec vocabulary; back to **agent**.
4. **agent** calls `product_search` with `rated_current_a` / poles facets or filters.
5. evidence gains SKU hits; agent may call `get_sku` for the shortlist winner.
6. **composer** writes an answer citing ordering codes and sources.
7. **validator** checks every stated ampere / pole count against evidence.
8. CLI prints the draft + validation JSON.

If the question was vague (“recommend an ACB”), planner may route through **clarify** once or twice before tools begin.

If the question was “distribution of breaking capacities across WiNmaster 3”, the
agent may call **`analytics_query`** once. Its sub-agent can run several focused SQL
queries and returns a factual summary with supporting numeric evidence; the main
agent owns any interpretation.

---

## 14. How to operate the system

```bash
# 1. Python deps
source /home/rohan/Nyalazone/cs_electric_agent/venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill ANTHROPIC_API_KEY / DATABASE_URL / etc.

# 2. Create or refresh derived views after loading product_chunks
make setup-db
make inspect

# 3. Run
export CS_BACKEND=postgres
python -m cs_agent.run --question "Compare two WiNmaster 3 ACB SKUs."

# 4. Offline tests
make test
```

After each wholesale reload of `in_use.product_chunks`, run `make refresh` so the views stay consistent with the source table.

---

## 15. What this POC deliberately does not do

Out of scope for v1 (by design):

- ingestion / re-embedding pipelines
- SQL guardrails beyond a future hook
- compatibility / accessory-matrix checking
- asset or curve retrieval
- multi-domain routing (FAQ, pricing desks, personas)
- page-level citations (provenance is source-file / source-of-truth level)

Known data quirks (mis-typed rows, POR pricing, duplicated family-level chunks, missing conditions on ratings) are **surfaced by tools and prompts**, not silently “fixed” in application code.

---

## 16. Suggested reading order in the code

1. `ARCHITECTURE.md` (this file)
2. `updated_implementation_plan.md` (canonical product plan)
3. `cs_agent/graph/build.py` (main flow)
4. `cs_agent/graph/nodes/*.py` (node behaviour)
5. `cs_agent/tools/registry.py` + `backends/postgres.py` (data access)
6. `cs_agent/db/views.sql` (derived schema)
7. `cs_agent/subgraphs/analytics/build.py` (SQL sub-agent)
8. `cs_agent/run.py` (CLI + checkpointer + interrupt loop)
