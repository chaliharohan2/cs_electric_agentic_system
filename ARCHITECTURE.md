# C&S Product Agent V2 — Architecture Guide

This document describes how the repository works end to end: what problem it
solves, how a question moves through the graph, how conversation context is
kept, what each tool does, and how the catalogue data is shaped underneath.

It is a system description, not a line-by-line code walkthrough. The
authoritative design notes live in [`product-agent-plan-v2.md`](product-agent-plan-v2.md);
this file explains what was actually built.

---

## 1. What this project is

C&S Electric sells a large electrical catalogue (circuit breakers, contactors,
switches, boards, and more). Product knowledge lives in PostgreSQL as brochure
and pricelist **chunks**: free text plus structured JSON facts and vector
embeddings.

This repository is a **CLI product-support agent** that answers questions over
that catalogue. Typical questions include:

- What does C&S offer in an area? (discovery)
- Which SKUs meet a numeric rating? (selection)
- How should I protect this application, and what C&S products fit? (advisory)
- What differs between these codes? (comparison)
- Which standards or IP ratings does C&S publish for this product? (compliance)

**Stack:** Python 3.11, LangChain, LangGraph, PostgreSQL + pgvector, psycopg
(no Flask/SQLAlchemy layer), OpenAI-compatible LLMs (Anthropic / vLLM) or
native Ollama, and `sentence-transformers` for query embeddings.

**Entry point:**

```bash
source /home/rohan/Nyalazone/cs_electric_agent/venv/bin/activate
python -m cs_agent.run --question "Which WiNbreak1 MCCB is rated 250 A?"
# multi-turn:
python -m cs_agent.run --thread-id customer-42
```

---

## 2. Repository layout

```text
cs_agent/
  run.py                 CLI: builds graph, checkpointer, clarify loop
  contracts.py           Pydantic plans, briefs, reports, gate/sufficiency types
  eval.py                Optional JSONL eval harness
  observability.py       JSONL + terminal trace of node/tool/LLM events
  tool_errors.py         Tool failures returned as tool results, not hard crashes

  config/
    endpoints.yaml       LLM profiles + node → profile map
    embeddings.yaml      Query embedding profiles (active: GTE 768-d)
    limits.yaml          Budgets and caps (env-overridable)
    limits.py            Typed loader for limits.yaml

  graph/
    build.py             Parent LangGraph topology and routing
    state.py             Shared parent state + reducers
    nodes/
      intake.py          Follow-up rewrite into a standalone question
      planner.py         Dispatch 1–5 specialist briefs
      clarify.py         Human interrupt for missing load-bearing params
      gate.py            Deterministic report-contract checks
      composer.py        Sufficiency check + final answer
      record_evidence.py Evidence extraction helpers (used by specialists)
      validator.py       Present but unwired

  subgraphs/
    agents/              Factory for the five private specialist graphs
    analytics/           SQL analytics sub-agent exposed as one tool

  tools/                 Schemas, descriptions, thin wrappers, registries
  backends/              CatalogBackend: postgres | fixtures
  db/                    views.sql + setup/refresh/inspect CLI
  embeddings/            Query embedding factory (GTE)
  llm/                   Model factory + structured JSON helper
  prompts/               Markdown prompts for every LLM node / specialist
  data/fixtures/         Synthetic catalogue for offline tests
  validation/            Numeric fidelity helpers (dormant validator)

tests/
  test_framework.py      Default offline suite (fixtures, no network/DB)
  test_vector_retrieval.py  Opt-in Postgres/GTE integration tests
```

Supporting docs:

- [`README.md`](README.md) — setup and run commands
- [`product-agent-plan-v2.md`](product-agent-plan-v2.md) — design source of truth
- [`product_chunks_schema_and_samples_v2.md`](product_chunks_schema_and_samples_v2.md)
  — live schema notes for `cs_electric_v2`

---

## 3. High-level shape

The v1 design was one tool-using agent. V2 is a **planner that dispatches
specialists in parallel**, then a **gate** and a **two-phase composer**:

```text
User question (CLI)
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ Parent LangGraph                                             │
│                                                              │
│  intake → planner ⇄ clarify                                  │
│              │                                               │
│              ├─ Send → discovery specialist (private tools)  │
│              ├─ Send → spec_selection …                      │
│              ├─ Send → solution_advisory …                   │
│              ├─ Send → comparison …                          │
│              └─ Send → compliance …                          │
│                        │                                     │
│                        ▼                                     │
│                      gate ──(retry failed only)──► specialists│
│                        │                                     │
│                        ▼                                     │
│               composer sufficiency                           │
│                   │                                          │
│                   ├─ targeted revision ──► specialists       │
│                   └─ compose_final → draft answer            │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
 CatalogBackend ──► Postgres mv_* views + product_chunks
                 └─► FixturesBackend (tests)
```

Important design rules:

1. **Parent `messages` hold only user-visible turns.** Specialist tool traffic
   stays inside each private subgraph so parallel Anthropic tool_use /
   tool_result pairs cannot interleave.
2. **Parallel writes use reducers.** Reports merge by agent name; evidence and
   tool-call counts add.
3. **Budgets are allocated before fan-out.** Mid-flight shared counters are not
   reliable under parallel `Send()`, so each specialist gets an allowance up
   front.
4. **The composer writes from specialist reports**, not from raw evidence dumps.

---

## 4. End-to-end turn flow

This section follows one user question from CLI start to final answer.

### 4.1 CLI entry (`run.py`)

1. Load `.env`.
2. Build a `TraceLogger` (JSONL file + optional screen summary).
3. Choose a checkpointer:
   - `CS_BACKEND=postgres` → `PostgresSaver` on `DATABASE_URL`, keyed by
     `thread_id`
   - otherwise → in-memory `MemorySaver`
4. Create initial parent state: the new human message, empty/reset reports, a
   session object, clarify/revision counters, and `turn_tool_calls_start`.
5. Invoke the compiled graph.
6. If the graph hits a clarify `interrupt`, prompt the user, then resume with
   `Command(resume=…)`.
7. Print `draft`. In interactive mode without `--question`, offer follow-ups on
   the same `thread_id`, carrying the previous turn’s `session` forward.

### 4.2 Intake

**Purpose:** turn a conversational follow-up into a self-contained question so
downstream nodes never need chat history.

- First turn (empty `session.turns`): pass the user text through unchanged;
  mark `is_followup=false`.
- Later turns: a cheap structured LLM call sees the session JSON and rewrites
  pronouns / references (“that one”, “compare those”) into explicit SKU codes
  or family names found in the session. It returns:
  - `standalone_question`
  - `referenced_skus`
  - `is_followup`
  - `carried_params` (merged into `session.resolved_params`)

Everything after intake works only from `standalone_question`.

### 4.3 Planner

**Purpose:** triage the question and dispatch work — not answer it.

The planner returns a structured `Plan`:

- `intent` and `strategy`
- `known_params` / `open_params`
- `needs_clarification`
- `dispatch`: one to five `AgentBrief`s

Each brief names an agent (`discovery`, `spec_selection`,
`solution_advisory`, `comparison`, `compliance`) and carries:

- `objective` — one sentence of what that specialist must establish
- `scope` — paths, families, or SKUs to stay inside
- `parameters` — numeric / categorical constraints already known
- `must_return` — concrete report contents required
- `allowance` — filled by the runtime, not the model

**Dispatch heuristics baked into the prompt:**

- Send every specialist whose report the answer needs; never unused agents.
- Product area + numeric requirement → discovery **and** spec_selection.
- Advisory almost always also gets spec_selection so recommendations land on
  real SKUs.
- Compliance is additive (“100 A MCCB that meets IEC …” → selection +
  compliance).

**Budget allocation** happens after the model returns:

```text
remaining = global_tool_budget − tools already used this turn
allowance = min(per_agent_tool_budget, remaining // n_dispatched)
```

Defaults (from `limits.yaml`, overridable with `CS_*`):

| Cap | Default |
|---|---|
| Global tool budget / turn | 100 |
| Per-agent tool budget | 20 |
| Clarify rounds | 2 |
| Gate retries | 1 (hard-coded routing) |
| Composer revision rounds | 2 |
| Tool failures / specialist | 3 |
| Analytics SQL queries / call | 4 |

If clarification is needed and the clarify cap is not exhausted, routing goes
to clarify; otherwise the planner forces progress and records assumptions.

### 4.4 Clarify

**Purpose:** ask only for parameters that would change which **family** is
recommended (load current, voltage, poles, breaking capacity, application
type, indoor/outdoor). Accessory suffixes and finishes are not asked.

1. The clarify node drafts at most three short questions.
2. LangGraph `interrupt()` pauses the run and surfaces the questions to the CLI.
3. The user’s answers are appended as a human message and stored in
   `session.resolved_params` so the same question is not asked again later.
4. Control returns to the planner.

### 4.5 Parallel specialist dispatch

When clarification is not needed, the planner route emits one LangGraph
`Send("specialist", …)` per brief. Those runs execute **in parallel**.

Each `Send` payload contains only:

- the brief (including allowance and any revision note)
- the standalone question

The specialist node invokes a **private compiled subgraph** for that role
(factory under `subgraphs/agents/`). When the subgraph finishes, the parent
receives:

- `reports[agent_name] = structured report`
- appended `evidence` rows tagged with the agent
- `tool_calls_made += tool_calls_used`

### 4.6 Inside one specialist

Every specialist uses the same loop shape:

```text
prepare → agent ⇄ tools → record → agent → … → report → END
```

| Step | What happens |
|---|---|
| **prepare** | Seed a private human message from the brief/objective; reset local call counters. |
| **agent** | LLM bound only to that role’s tools. System prompt = shared `agent_common.md` + role body under `prompts/agents/`. Remembers remaining allowance and failure count. |
| **tools** | LangGraph `ToolNode` executes the requested catalogue/analytics tools. Errors become tool results (with hints), not graph crashes. |
| **record** | Trailing tool messages are turned into evidence rows (facts, names, document snippets, analytics statements) and tagged with the agent name. Call/failure counters update. |
| **report** | Structured Pydantic report for that role (`DiscoveryReport`, `SpecSelectionReport`, …). Spec findings must carry a `SourceRef` with `sku_code`. |

Routing stops tool use when:

- the model makes no further tool calls, or
- the next batch would exceed the remaining allowance, or
- tool failures hit the per-agent failure limit

Then the report node always runs.

### 4.7 Gate (deterministic, no LLM)

After all current specialist branches finish, the gate validates each
dispatched report against a structural contract:

| Agent | Must satisfy |
|---|---|
| discovery | ≥1 family, and ≥1 representative SKU **or** an explicit gap explaining why none |
| spec_selection | ≥1 candidate **or** (`no_candidates_reason` + non-empty `filters_tried`) |
| comparison | non-empty axes and ≥2 SKU rows, or `status=no_result` with a reason |
| compliance | ≥1 standards claim **or** non-empty `not_established` |
| solution_advisory | ≥1 catalog_backed or engineering_guidance claim; every recommended slot resolved to a family/SKU or explicitly “no C&S product” |
| all agents | any `Finding` of kind `specification` must cite a `SourceRef.sku_code` |

On failure, the gate may **re-Send only the failing agents once**, appending the
violations as a `revision_note` on their briefs. This is what keeps weaker
local models from “browsing forever and never looking up a SKU.”

If contracts pass (or the retry budget is spent), routing continues to the
composer.

### 4.8 Composer — phase 1: sufficiency

A structured LLM call inspects the specialist reports and returns:

```text
{ sufficient: bool, gaps: [{ agent, missing, suggested_tool }] }
```

Rules:

- Gaps must be concrete and retrievable — never “re-run everything.”
- If insufficient, revision rounds remain, and tool budget remains, only the
  named agents are re-dispatched with a gap brief.
- If the global budget for the turn is exhausted, sufficiency is forced true
  with a `budget_exhausted` flag so the final answer can disclose incomplete
  evidence.

### 4.9 Composer — phase 2: final answer

`compose_final` writes the user-facing answer from:

- the specialist reports JSON
- recorded assumptions
- the standalone question

It does **not** call tools. Citation policy is report-driven:

- brochure → `.md` filename, no page
- pricelist → PDF + page when present
- code grammar → say the value was derived from the ordering code
- prices respect all seven `price_status` values; never quote
  `multiple_variants` or a context-mismatched observation

After drafting, the composer **updates session memory** for the next turn:

- append a compact turn summary
- refresh `focus_skus` from cited / candidate / representative codes
- refresh `focus_family` when discovery provided one
- store `prior_reports`

The draft is what the CLI prints. The numeric validator node still exists in
the package but is **not wired** into the graph.

---

## 5. Multi-turn / contextual behaviour

“Context” in this system is deliberately **not** “dump the whole chat into
every specialist.” It is a small, typed session object plus a rewritten
standalone question.

### 5.1 Session object

```text
session = {
  turns: [{ question, intent, agents_used, answer_summary }],
  focus_skus: [...],          # SKUs the conversation is currently about
  focus_family: str | None,
  resolved_params: {...},     # clarify answers and carried params
  prior_reports: {...}        # last turn’s specialist reports
}
```

### 5.2 Persistence

- `thread_id` selects a LangGraph checkpoint lane.
- With Postgres backend, `PostgresSaver` persists graph state across process
  restarts.
- The CLI also passes the previous `session` dict into the next
  `run_question()` so follow-ups work even when starting a fresh invoke with a
  reset reports map.

### 5.3 What each layer sees

| Layer | Sees |
|---|---|
| Intake | Raw user message + full session JSON |
| Planner / clarify / specialists / composer | Standalone question (+ briefs / reports as appropriate) |
| Specialists | Private tool transcripts only for their own run |

So “compare that to X” becomes something like “Compare SKU-A with SKU-X …”
before planning. Specialists never have to resolve “that.”

### 5.4 Per-turn budgets under a long thread

`tool_calls_made` is cumulative in checkpointed state (reducer adds). Intake
records `turn_tool_calls_start` so planner / gate / composer compute remaining
budget **for this turn only**.

---

## 6. The five specialists

All share `agent_common.md` (identifiers, value kinds, composite exclusions,
price caveats, taxonomy rules). Role bodies add method and report shape.

| Specialist | Job | Typical tools |
|---|---|---|
| **discovery** | Map what C&S sells in an area; return families + representative SKUs | taxonomy_browse, product_search, get_peer_group, search_documents |
| **spec_selection** | Ranked shortlist meeting numeric/spec filters | list_canonical_specs, product_search, get_sku, get_price_detail, analytics_query |
| **solution_advisory** | Engineering reasoning + catalogue mapping, claims kept separate | taxonomy_browse, product_search, search_documents, get_sku |
| **comparison** | Side-by-side table; prefer catalogue `comparable_on` when peers match | resolve_product, get_peer_group, compare_skus, get_price_detail |
| **compliance** | Published standards / tests / IP / certifications only | list_canonical_specs (topic search), get_sku, search_documents (`standards`) |

Shared tools bound to every specialist: `resolve_product`, `product_search`,
`get_sku`.

Reports are role-specific Pydantic models in `contracts.py`. The gate and
composer both depend on those shapes.

---

## 7. Tools and how they work

Tools are LangChain structured tools. Thin wrappers in `tools/impl.py` call a
`CatalogBackend`. Production uses `PostgresBackend` over materialized views;
tests use `FixturesBackend` with synthetic JSON.

### 7.1 Agent ↔ tool matrix

| Tool | discovery | spec_sel | advisory | comparison | compliance |
|---|:--:|:--:|:--:|:--:|:--:|
| resolve_product | ● | ● | ● | ● | ● |
| product_search | ● | ● | ● | ● | ● |
| get_sku | ● | ● | ● | ● | ● |
| taxonomy_browse | ● | ● | ● | ○ | ○ |
| list_canonical_specs | ○ | ● | ● | ● | ● |
| search_documents | ● | ○ | ● | ○ | ● |
| get_price_detail | ○ | ● | ○ | ● | — |
| compare_skus | — | ○ | — | ● | — |
| get_peer_group | ● | ○ | — | ● | — |
| analytics_query | — | ● | — | ● | — |

● primary / always bound · ○ available · — not bound

### 7.2 Individual tools

**`resolve_product`**
Three-stage cascade, stop at first hits:

1. Exact match on `mv_code_alias` (normalised spelling)
2. Trigram fuzzy match on codes (`similarity ≥ 0.35`)
3. Description / family trigram + full-text over chunk content

Returns ranked candidates, `resolution` mode, and an alias note when the user
typed a non-canonical spelling. Always use this before SKU-specific tools when
the user typed a code.

**`taxonomy_browse`**
Walk the 2–4 level catalogue `path` one level at a time. Returns children with
SKU counts, leaf flags, and published description/URL from `levels[]`.
`_no_category` children are returned in a separate **uncategorised** block
(pricelist section names, not published categories). Optional facets at leaf
level come from `mv_facet`. Browsing alone is never a product answer.

**`list_canonical_specs`**
Family-level vocabulary from `mv_spec_registry`: spec IDs, units, value kinds,
canonical flag, SKU counts, composite counts, observed min/max.
`spec_id_contains` lets compliance discover topics (`standard`, `test`, `ip`)
at runtime instead of hardcoding names.

**`product_search`**
Primary structured finder. Filters by path prefix, family, facets, market
segment, price status, chunk presence, free text, and typed spec predicates:

| op | Meaning |
|---|---|
| gte / lte / eq | Range-aware numeric predicates on min/max/value |
| contains | Substring on `value_display` |

Response envelope always includes `hits`, `total_matched`,
`composite_excluded`, `filters_applied`, and `widening_hint` on empty results.
**Composite values cannot satisfy numeric predicates**; they are counted as
unknown, not ruled out.

**`get_sku`**
Full detail for one resolved code: facts, decoded axes, sources, extraction
missing/confidence, optional chunks (by `chunk_type`), price, and peers.
`extraction.missing` means “not published by C&S,” never zero.

**`get_price_detail`**
Provenance-aware pricing from `mv_price`. Surfaces every observation plus
`price_status` and `quotable`. Quoting is false for `multiple_variants` or when
every observation’s context names a different code
(`context_names_own_code=false`). Prices are MRP inclusive of GST.

**`get_peer_group`**
Returns the catalogue peer set, `comparable_on` axes, related codes, and peer
decoded differences. Used for shortlists and like-for-like comparison.

**`compare_skus`**
Side-by-side pivot for 2–10 codes. If they share a peer group, axes default to
the intersection of `comparable_on`; otherwise the union of present specs.
Returns `peer_group_match` and `axes_source`. Empty cells mean not published.

**`search_documents`**
Qualitative retrieval only (features, application, installation, standards
prose). Requires a family or path prefilter. Flow:

1. If any matching rows have embeddings → embed the query with
   **Alibaba-NLP/gte-base-en-v1.5** (normalized 768-d), rank by pgvector cosine
   distance, dedupe identical content by md5, attach brochure refs from
   `mv_source`, return `mode: "vector"`.
2. If zero vector hits (or no embeddings present) → one retry on `content_tsv`
   full-text, return `mode: "lexical"`.

Never use this for numeric rating lookup. Corpus embedding **ingestion** is
external to this repo; query embedding happens at tool-call time.

**`analytics_query`**
Delegates multi-step SQL analysis to a private analytics subgraph
(`prepare → analyst ⇄ execute_analytics_sql → summarize`). The analyst may run
several read-only SELECTs against the v2 views (capped by
`analytics_max_queries`) and returns a factual summary with numeric evidence —
no recommendations. Used when ranking/aggregating many SKUs is awkward with
the structured tools alone.

### 7.3 Tool failure behaviour

Raised exceptions and backend `{error: …}` payloads both count as failures.
The model sees a JSON error with an optional hint (for example, wrong filter
value type) and may retry. After the failure limit, the specialist stops
calling tools and reports with what it has.

---

## 8. Catalogue data model

### 8.1 Source table

`in_use.product_chunks` in database **`cs_electric_v2`** is the denormalised
source of truth. Roughly:

- `content` — chunk text
- `embedding vector(768)` — GTE vectors (loaded externally)
- `content_tsv` — generated English tsvector for lexical fallback
- `taxonomy` — `path`, `levels`, `depth`, `headings` (no `category` key)
- `product` — `sku_code`, aliases, family, peer group, price status/observations, decoded axes, …
- `details` — facts, sources, extraction metadata
- `chunk_type` — one of ~19 values; one row per `(product_id, chunk_type)` in practice

Live scale after setup: about **9,115** products and **79,297** chunks.

### 8.2 Why materialized views

Querying nested JSON repeatedly is slow and error-prone. `cs_agent/db/views.sql`
projects eight views:

| View | Role |
|---|---|
| `mv_sku` | One row per product: path, aliases, peers, extraction, price observations |
| `mv_code_alias` | sku / canonical / alias resolution surface |
| `mv_fact` | Long typed facts with range + composite support |
| `mv_price` | Price observations + context mismatch detector |
| `mv_source` | Typed citation refs (brochure_md, pricelist_pdf, product_page) |
| `mv_spec_registry` | Per-family spec vocabulary and observed bounds |
| `mv_facet` | Decoded ordering-code axes keyed by family |
| `mv_chunk_index` | Chunk presence / headings without scanning 79k rows |

Helper `in_use.safe_num` converts only clean numeric strings so one dirty cell
cannot abort a whole refresh.

Refresh order:

```text
mv_sku
  → mv_code_alias, mv_fact, mv_price, mv_source
  → mv_spec_registry, mv_facet, mv_chunk_index
```

Commands:

```bash
make setup-db   # extensions, content_tsv, embedding type guard, recreate views
make refresh    # refresh existing views after a data reload
make inspect    # products/chunks/embeddings/view counts + embedding dimension
```

Setup migrates an **empty** embedding column to `vector(768)` and refuses if
populated embeddings already exist at a different dimension.

### 8.3 Catalogue semantics the agents must respect

- **`sku_code`** is the only product identifier returned to users.
- The same product may appear under alternate spellings (`also_published_as`,
  `canonical_code`).
- Spec `value_kind` may be scalar, range, set, text, or **composite**.
- `source_of_truth` distinguishes pricelist table, brochure, catalogue, and
  code-grammar (derived) claims.
- Path depth is 2–4; deepest level is the family.
- Seven price statuses exist; price is never a plain numeric fact.

---

## 9. Models, embeddings, and configuration

### 9.1 LLM routing

`cs_agent/config/endpoints.yaml` defines profiles (`sonnet`, `qwen_*`,
`ollama_*`) and a node map. Current nodes:

- `intake`, `planner`, `clarify`, `composer`
- `agent` — **shared by all five specialists**
- `analytics.write_sql`, `analytics.shape`

Override with `CS_MODELS`, for example:

```bash
CS_MODELS=all:ollama_35b
CS_MODELS=agent:qwen_a3b,composer:sonnet
```

Anthropic and vLLM use the OpenAI-compatible client; Ollama uses `ChatOllama`.
Structured outputs go through `cs_agent.llm.structured`, which validates JSON
against a Pydantic schema and retries on validation failure — important for
local models that ignore strict schema modes.

### 9.2 Query embeddings

Active profile in `embeddings.yaml`:

```text
gte_base_en_v1_5 → Alibaba-NLP/gte-base-en-v1.5, 768-d, normalize=true,
                   trust_remote_code=true
```

Override with `CS_EMBEDDING_MODEL`. Runtime checks that the profile dimension
matches `product_chunks.embedding`. GTE’s custom modeling currently requires
`transformers>=4.44,<5` (pinned in `requirements.txt`).

---

## 10. Observability and evaluation

Every run appends structured events to `CS_LOG_FILE`
(default `logs/cs_agent_trace.jsonl`): run lifecycle, node enter/exit,
transitions, state snapshots/updates, LLM and tool activity, interrupts, and
errors. Terminal output is a shorter human summary of the same stream
(`CS_LOG_TO_SCREEN`).

Because specialists fan out in parallel, every event carries an `agent` field
naming the sub-agent that produced it, and the terminal prefixes each line with
it (`[coverage] 🔧 sku_lookup(…)`). The label comes from `cs_agent` metadata
attached by `agent_scoped_config` when a subgraph is invoked, and it is
inherited by all nested runs; work the analytics subgraph performs for a
specialist is labelled `coverage/analytics`. Filter one agent's activity out of
a trace with `jq 'select(.agent == "coverage")'`.

`cs_agent/eval.py` is a small JSONL harness that runs cases through
`run_question` and reports per-agent dispatch accuracy and endpoint profile
metadata. It is optional and intended for offline benchmarking, not the
default unit suite.

---

## 11. Tests and operations

Use the project venv for every command:

```bash
source /home/rohan/Nyalazone/cs_electric_agent/venv/bin/activate
```

| Command | Meaning |
|---|---|
| `make test` | Fixtures-only unit suite (`tests.test_framework`) — no DB, no HF download |
| `make test-vector` | Opt-in vector suite; needs Postgres + loaded 768-d embeddings + `CS_VECTOR_TEST_FAMILY` |
| `make setup-db` / `make refresh` / `make inspect` | Catalogue projection lifecycle |
| `python -m cs_agent.run …` | Interactive or one-shot answering |

`tests/test_vector_retrieval.py` is deliberately excluded from `make test` and
gated by `CS_RUN_VECTOR_TESTS=1`.

---

## 12. Mental model of one successful answer

1. User asks a follow-up about “that MCCB” on an existing thread.
2. Intake rewrites it to an explicit SKU/family question using session focus.
3. Planner dispatches discovery + spec_selection (and maybe compliance).
4. Specialists privately call structured tools, record evidence, and emit typed
   reports with sources and gaps.
5. Gate bounces any report that browsed families but never produced SKUs or
   reasons; one targeted retry is allowed.
6. Composer checks sufficiency; if a standards claim is still missing it
   re-sends only compliance with that gap.
7. Final answer is written from the reports, citations included, session
   updated for the next turn.

That separation — **rewrite → plan → retrieve in parallel → structurally
check → revise narrowly → compose from reports** — is the core of the v2
architecture.
