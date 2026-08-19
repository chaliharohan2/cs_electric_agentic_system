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

**Stack:** Python 3.11, LangChain, LangGraph, SQLite catalogue artifact
(`sku_fact` + `chunk` + sqlite-vec), OpenAI-compatible LLMs (Anthropic / vLLM)
or native Ollama, and `sentence-transformers` for query embeddings.

**Entry point:**

```bash
source /home/rohan/Nyalazone/cs_electric_agent/venv/bin/activate
# build the catalogue once (needs DATABASE_URL + refreshed mv_* views)
python scripts/build_sqlite.py
CS_BACKEND=sqlite python -m cs_agent.run --question "Which WiNbreak1 MCCB is rated 250 A?"
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
    contact.yaml         Where an out-of-scope enquiry is sent (site + phone)
    contact.py           Typed loader for contact.yaml

  graph/
    build.py             Parent LangGraph topology and routing
    state.py             Shared parent state + reducers
    digest.py            Compact a finished report for the next stage
    nodes/
      intake.py          Follow-up rewrite into a standalone question
      planner.py         Choose the specialists and order them into stages
      clarify.py         Human interrupt for missing load-bearing params
      gate.py            Deterministic report-contract checks
      composer.py        Sufficiency check + final answer
      out_of_scope.py    Reply to a turn the catalogue pipeline never runs for
      record_evidence.py Evidence extraction helpers (used by specialists)
      validator.py       Present but unwired

  subgraphs/
    agents/              Factory for the five private specialist graphs
    analytics/           SQL analytics sub-agent exposed as one tool

  tools/                 Schemas, descriptions, thin wrappers, registries
  backends/              CatalogBackend: sqlite | fixtures
  db/                    Postgres mv_* views.sql + setup/refresh (build source)
  embeddings/            Query embedding factory (GTE)
  llm/                   Model factory, structured JSON helper, streamed generation
  prompts/               Markdown prompts for every LLM node / specialist
  data/fixtures/         Synthetic catalogue for offline tests
  validation/            Numeric fidelity helpers (dormant validator)

scripts/
  build_sqlite.py        Postgres mv_* → artifacts/catalog-*.sqlite

artifacts/               Built catalogue .sqlite (gitignored) + build_report.json
state/                   LangGraph SqliteSaver checkpoints (gitignored)

tests/
  test_framework.py      Default offline suite (fixtures, no network/DB)
  test_sqlite.py         SQLite backend unit tests on a mini catalog
  test_vector_retrieval.py  Opt-in SQLite/GTE integration tests
```

Supporting docs:

- [`README.md`](README.md) — setup and run commands
- [`SQLITE-CATALOG.md`](SQLITE-CATALOG.md) — SQLite schema, JSON shapes, and build snapshot
- [`product-agent-plan-v2.md`](product-agent-plan-v2.md) — multi-agent design
- [`product-agent-plan-v2-sqlite-db-plan.md`](product-agent-plan-v2-sqlite-db-plan.md)
  — SQLite data-layer migration
- [`product_chunks_schema_and_samples_v2.md`](product_chunks_schema_and_samples_v2.md)
  — live schema notes for `cs_electric_v2`

---

## 3. High-level shape

The v1 design was one tool-using agent. V2 is a **planner that orders
specialists into stages**, then a **gate** and a **two-phase composer**:

```text
User question (CLI)
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ Parent LangGraph                                             │
│                                                              │
│  intake → planner ⇄ clarify                                  │
│              │                                               │
│              ├─ scope ≠ catalogue ─► out_of_scope ─► END     │
│              ▼                                               │
│      ┌─► stage N: Send → one specialist per brief            │
│      │            (parallel only within the stage)           │
│      │              │                                        │
│      │              ▼                                        │
│      │            gate ──(retry this stage's failures)──┐    │
│      │              │                                   │    │
│      └──────────────┤◄──────────────────────────────────┘    │
│      (stage N+1,    │                                        │
│       with stage N's│ no stages left                         │
│       digest)       ▼                                        │
│               composer sufficiency                           │
│                   │                                          │
│                   ├─ targeted revision ──► specialists       │
│                   └─ compose_final → draft answer            │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
 CatalogBackend ──► SqliteBackend (artifacts/catalog-latest.sqlite)
                 └─► FixturesBackend (tests)
```

Important design rules:

1. **Parent `messages` hold only user-visible turns.** Specialist tool traffic
   stays inside each private subgraph so parallel Anthropic tool_use /
   tool_result pairs cannot interleave.
2. **Parallel writes use reducers.** Reports merge by agent name; evidence and
   tool-call counts add; `stage_index` takes the last write, which is safe
   because every branch in a stage writes the same number.
3. **Specialists are ordered, not simultaneous.** Agents depend on each other —
   discovery finds the families spec_selection filters — so the planner assigns
   each brief a stage, and a stage starts only when the one before it has
   finished. Agents share a stage only when neither needs the other's output.
4. **A later stage receives digests, not full reports.** `graph/digest.py`
   reduces each finished report to the identifiers a downstream agent can act
   on, so the pipeline passes findings forward without re-retrieving them and
   without copying whole reports into every prompt.
5. **Budgets are allocated per stage, at dispatch.** Mid-flight shared counters
   are not reliable under parallel `Send()`, so a stage's agents get a fixed
   allowance up front — but that allowance is sized from what earlier stages
   actually spent, so an unused budget carries forward.
6. **The composer writes from specialist reports**, not from raw evidence dumps.
7. **A question the catalogue cannot answer leaves before it costs anything.**
   Scope is decided by the planner call that already happens, so the cheap path
   is genuinely cheap: no specialist, no tool, no gate, no sufficiency pass.

---

## 4. End-to-end turn flow

This section follows one user question from CLI start to final answer.

### 4.1 CLI entry (`run.py`)

1. Load `.env`.
2. Build a `TraceLogger` (JSONL file + optional screen summary).
3. Choose a checkpointer:
   - `CS_BACKEND=sqlite` → `SqliteSaver` on `state/checkpoints.sqlite`
   - `CS_BACKEND=fixtures` → in-memory `MemorySaver`
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

**Purpose:** triage the question, then decide **which** specialists run and **in
what order** — not answer it.

The planner returns a structured `Plan`:

- `scope` and `scope_note` — see below
- `intent` and `strategy`
- `known_params` / `open_params`
- `needs_clarification`
- `dispatch`: one to five `AgentBrief`s, or none when scope is not `catalogue`

Each brief names an agent (`discovery`, `spec_selection`,
`solution_advisory`, `comparison`, `compliance`) and carries:

- `stage` — 1-based execution stage; agents sharing a stage run in parallel
- `objective` — one sentence of what that specialist must establish
- `scope` — paths, families, or SKUs to stay inside
- `parameters` — numeric / categorical constraints already known
- `must_return` — concrete report contents required
- `allowance` — filled by the runtime at dispatch, not by the model

**Agent roles**, as the prompt states them:

| Agent | Entry question | Produces |
|---|---|---|
| `discovery` | “What do you have in MCCBs?” — or a vague ask, entered through the application segment (home, panel, plant, substation) | Families with descriptions, URLs and SKU counts, plus follow-up questions at `overview` depth or representative codes at `detailed` |
| `spec_selection` | “A 400 A 4-pole changeover” | The missing criticals, then a ranked shortlist of ordering codes |
| `solution_advisory` | “Protection scheme for an 11 kV feeder”, “AMF for 2×500 kVA gensets” | A multi-category scheme: one resolved slot per function |
| `comparison` | “Winbreak or Winbreak 2?” | A difference table over named products or a peer set |
| `compliance` | IS/IEC conformity, CPRI type tests, certifications, catalogue and manual requests | Standards claims, or `not_established` with what was searched |

**Ordering rules baked into the prompt:**

- Dispatch the fewest agents that can answer; one is normal, two common, three
  only when the question genuinely has three parts.
- `discovery` precedes `spec_selection` unless the question already names the
  product area — in which case discovery is not dispatched at all.
- `comparison` and `compliance` need ordering codes, so they follow whichever
  agent produces them, unless the user supplied the codes.
- `solution_advisory` **leads**: it decides which functions a scheme needs, so
  any `spec_selection` or `compliance` work follows it. It is never a commentary
  layer over a single-product answer.
- Never dispatch an agent to review or confirm another's work, and never
  dispatch two agents that would run the same searches.

`Plan` validation renumbers stages to a contiguous `1..N` and keeps one brief
per agent, so a model that emits stages `1` and `3`, or lists an agent twice,
still yields a runnable pipeline. The planner node then clamps any stage above
`max_stages` onto the last stage — an over-long plan runs flatter rather than
losing an agent.

**Answer depth.** Every brief also carries a `depth`, which the planner sets and
which decides how far the specialist retrieves:

| Depth | Answers at | Tool ceiling | Discovery must return |
|---|---|---|---|
| `overview` | Range level: which families exist, what each is for | `overview_tool_budget` (6) | ≥1 family and ≥1 `follow_up_question`; ordering codes are **not** required |
| `detailed` | Ordering codes and the specifications the brief names | `per_agent_tool_budget` (20) | ≥1 family and ≥1 representative SKU or an explicit gap |

A plan that names no depth gets `overview` for `discovery` and `detailed` for
everyone else (`DEFAULT_DEPTH` in `contracts.py`, applied by `Plan` validation).
The default runs that way round deliberately: a planner that forgets the field
produces a cheap answer that asks a question back, rather than an exhaustive
catalogue sweep.

Depth exists because breadth was previously emergent. Asked "what air circuit
breakers do you have", discovery spent 19 tool calls and 14 minutes deriving
current bands per family — an answer that the single `taxonomy_browse` call at
`Circuit Breakers > Air Circuit Breakers` already contained in 1.4 kB. Three
things drove it, and all three had to change together: the gate demanded a
representative SKU, `agent_common.md` told every specialist that browsing is not
a product answer, and a 20-call budget with no stopping rule reads as work still
to do. Relaxing any one alone would have been overridden by the others — a
softened prompt still fails the gate, and a failed gate spends a retry.

The follow-up questions are **not** the clarify mechanism. Clarify interrupts
before planning and blocks on an answer; `follow_up_questions` ride out with a
delivered answer and invite the next turn. Whether that next turn is `detailed`
is again the planner's call — nothing infers it from `is_followup`.

**Budget allocation** happens per stage, at dispatch:

```text
remaining = global_tool_budget − tools already used this turn
allowance = min(per_agent_tool_budget, remaining // n_in_this_stage)
if depth == "overview": allowance = min(allowance, overview_tool_budget)
```

Because it is recomputed when each stage starts, a cheap first stage leaves its
unspent budget to the stages behind it. The depth cap is applied in `_send`, so
it holds on every path that reaches a specialist: first dispatch, gate retry,
and composer revision.

Defaults (from `limits.yaml`, overridable with `CS_*`):

| Cap | Default |
|---|---|
| Global tool budget / turn | 100 |
| Per-agent tool budget | 20 |
| Overview tool budget | 6 |
| Revision tool budget (gate retry, resumed) | 5 |
| Stages per plan | 3 |
| Clarify rounds | 2 |
| Gate retries | 1 per stage (hard-coded routing) |
| Composer revision rounds | 2 |
| Tool failures / specialist | 3 |
| Analytics SQL queries / call | 4 |
| Peer rows / `get_peer_group` | 25 |
| Chars / chunk of brochure text | 1500 |
| Facet rows / `taxonomy_browse` | 60 |
| Chars / analytics spec registry | 24000 |

If clarification is needed and the clarify cap is not exhausted, routing goes
to clarify; otherwise the planner forces progress and records assumptions.

**Scope.** Before any of that, the planner sets `scope`:

| `scope` | What it covers | Routing |
|---|---|---|
| `catalogue` | Products, ranges, codes, ratings, prices, standards, datasheets, or which C&S product suits an installation | Normal pipeline |
| `company` | A real C&S enquiry for another desk: careers, an order, a complaint, warranty, dealership, accounts | `out_of_scope` → END |
| `unrelated` | No C&S connection — general how-to with no product question behind it, another manufacturer, off-topic | `out_of_scope` → END |

It rides on the planner call that already happens, which is the whole point: a
separate classifier node would add a round trip to **every** turn to catch the
rare one. `Plan.dispatch` therefore cannot carry a `min_length` any more, so
`_require_dispatch_in_scope` enforces the floor of one agent for `catalogue`
plans only — `structured()` retries a planner that returns neither.

Scope is checked **before** `needs_clarification`. Asking a job applicant for a
pole count is worse than not answering them.

The prompt biases hard toward `catalogue`, because the two failure modes are not
symmetric: answering a lightbulb question costs a wasted run, while refusing a
real product question costs a customer. A question that mentions an
installation, a load, an application or a standard is `catalogue` even when it
names no product — working out which product fits *is* the job.

### 4.4 Clarify

**Purpose:** ask only for parameters that would change which **family** is
recommended (load current, voltage, poles, breaking capacity, application
type, indoor/outdoor). Accessory suffixes and finishes are not asked.

1. The clarify node drafts at most three short questions.
2. LangGraph `interrupt()` pauses the run and surfaces the questions to the CLI.
3. The user’s answers are appended as a human message, stored in
   `session.resolved_params`, and folded into `standalone_question` so the
   planner, specialists, and composer all see them.
4. Control returns to the planner, which receives `known_params` (not only the
   original question) and copies them into every dispatch brief.

### 4.5 Staged specialist dispatch

When clarification is not needed, the planner route emits one LangGraph
`Send("specialist", …)` per brief **in the first stage only**. Agents in that
stage run in parallel; later stages wait. After the gate accepts a stage,
`_after_gate` emits the next stage's `Send`s, so the pipeline advances one
stage per `specialist → gate` cycle until no stages remain.

Each `Send` payload contains:

- the brief (stage, allowance, merged parameters, any revision note)
- the standalone question
- `upstream` — the digested reports of every earlier stage

`upstream` is what makes ordering worth the latency. `graph/digest.py` reduces
each finished report to the identifiers a downstream agent can act on —
families, representative and candidate SKUs, advisory slots, compared codes,
standards claims, gaps — and drops findings, sources and prose. `prepare` puts
it on the specialist's opening turn under “Already established by earlier
stages”, and `agent_common.md` instructs the agent to build on it rather than
retrieve it again.

The specialist node invokes a **private compiled subgraph** for that role
(factory under `subgraphs/agents/`). When the subgraph finishes, the parent
receives:

- `reports[agent_name] = structured report`
- appended `evidence` rows tagged with the agent
- `tool_calls_made += tool_calls_used`
- `stage_index = the stage that just ran`

### 4.6 Inside one specialist

Every specialist uses the same loop shape:

```text
prepare → agent ⇄ tools → record → agent → … → report → END
           (streamed)                                (streamed)
```

| Step | What happens |
|---|---|
| **prepare** | Seed a private human message from the brief/objective; reset local call counters. |
| **agent** | LLM bound only to that role’s tools. System prompt = shared `agent_common.md` + role body under `prompts/agents/`. Remembers remaining allowance and failure count. Streams to screen under the agent's name (§10.1). |
| **tools** | A wrapper around LangGraph's `ToolNode` (`subgraphs/agents/tool_node.py`) executes the requested tools. Errors become tool results (with hints), not graph crashes. A call whose name and arguments exactly match one already answered in this transcript is short-circuited with a pointer to it rather than re-executed — see "Repeat calls" below. |
| **record** | Trailing tool messages are turned into evidence rows (facts, names, document snippets, analytics statements) and tagged with the agent name. Call/failure counters update. |
| **report** | Structured Pydantic report for that role (`DiscoveryReport`, `SpecSelectionReport`, …). Spec findings must carry a `SourceRef` with `sku_code`. Runs as a continuation of the agent's own conversation, not a fresh call — see "Why the report reuses the thread" below. Streams too: it is the largest generation in a turn. |

Routing stops tool use when:

- the model makes no further tool calls, or
- the next batch would exceed the remaining allowance, or
- tool failures hit the per-agent failure limit

Then the report node always runs.

**Why the report reuses the thread.** The report call sends the same system
prompt the loop used, then the loop's own messages, then the instruction and
schema as one trailing human message. It looks redundant — the model just saw
all of it — and it is the single largest latency saving in the pipeline.

The node used to build a fresh `SystemMessage` and one large JSON payload
holding `brief`, `question`, a rendered `transcript`, *and* the `evidence` rows.
The last two are the same tool outputs in two encodings: on the measured run the
payload was 407,618 characters, of which `evidence` was 214,427 and 79% of those
records were spec-registry rows rather than product facts. Worse, a fresh system
prompt shares no prefix with the loop that just ran, so none of it hit the
server's KV cache: report calls prefilled at 642 tok/s against the 2,771 tok/s
the agent loop was getting on the identical text. One report call took 422s.

Continuing the thread makes the prefix free and hands the model the tool results
in their original form. Three constraints hold it together, and each was found
by measurement rather than reasoning:

1. `_system_prompt` is shared by both nodes, so the prefix is byte-identical.
2. The schema rides in the **last** message, not the first: `structured()`
   prepends its schema hint unless one is already present, which would put a
   fresh 5.8k-character system message ahead of the transcript.
3. The loop's tools stay **bound** on the report call. A server renders tool
   schemas into the prompt prefix, so the same messages sent without tools are
   a different prefix. Measured against Ollama directly: identical text
   prefills at 91,611 tok/s with tools bound and repeated, and at 808 tok/s —
   cold, indistinguishable from a first call — with the tools removed. The
   report is still told not to call one; they are bound for the prefix, not
   offered for use.

`evidence` no longer goes to the model at all; it is still accumulated into
`AgentState` for the (dormant) validator.

Because the report node reads the same conversation, the loop must not write the
report itself. Left to its own devices the specialist ends its last turn with the
report in prose — 4,423 characters of it on one measured run — which the report
node then regenerates as JSON. The prose is discarded, and generating it cost
about 100s on a model decoding at 11 tok/s. `agent_common.md` therefore states
that retrieval is the loop's whole job and that it should finish with one short
sentence and no tool call.

**Malformed tool calls.** Ollama's tool-call parser sometimes splits a name
across two calls when the model emits Qwen's XML form rather than the JSON it
expects. Asked "What do you have in wim trip?", qwen3.8 produced
`cat\n</parameter` and `alogue_map` for a single `catalogue_map`, and the run
had to be killed. Three things were wrong, and each is now handled:

1. **The stream is re-read.** `generate` is given the names of the tools bound
   to the model, and a streamed reply naming a tool none of them has is re-run
   unstreamed — the batch parser is the more robust of the two. It is logged as
   `llm.stream_reparse`. Showing the work is never worth getting it wrong.
2. **A repeat of a *failed* call is no longer short-circuited.** `_earlier_calls`
   used to record every call regardless of outcome, so the second identical
   broken call came back as a plain success with no `error` field. That laundered
   a failure into a non-failure: `tool_failures` stopped rising, the failure
   limit never tripped, and the loop span until it was interrupted. Only calls
   that succeeded are short-circuited now; re-running a failed one costs the same
   error again, and the budget ends it.
3. **An unknown name gets an error worth reading.** LangGraph's own message lists
   every tool and stops there, leaving the model to work out that its *syntax*
   was wrong rather than its choice of tool. The wrapper says so, and where the
   wreckage still contains a fragment matching exactly one bound tool — `cat` and
   `alogue_map` both reach `catalogue_map` — it names it. Only an unambiguous
   match is offered; naming the wrong tool is worse than naming none. Valid calls
   in the same batch still run.

**Repeat calls.** Specialists re-issue calls they have already made — one
measured run called `list_canonical_specs(family="Switch Sockets")` four times
unchanged after the first returned nothing. The tool node answers an exact
repeat with `{"repeat_of_call": n, ...}` instead of re-running it, which costs a
few tokens rather than a few thousand and says the thing a second identical call
cannot discover for itself: the arguments have to change. Mixed batches still
run their fresh calls, and every call the model made gets a result, because a
tool call left unanswered makes the thread invalid at most providers.

### 4.7 Gate (deterministic, no LLM)

After a stage's specialist branches finish, the gate validates **that stage's**
reports against a structural contract. It ignores briefs belonging to later
stages: those have not run, so gating them would fail every one of them and
spend the retry budget on work never dispatched.

| Agent | Must satisfy |
|---|---|
| discovery (`detailed`) | ≥1 family, and ≥1 representative SKU **or** an explicit gap explaining why none |
| discovery (`overview`) | ≥1 family, and ≥1 `follow_up_question`. Ordering codes are not the deliverable at this depth |
| spec_selection | ≥1 candidate **or** (`no_candidates_reason` + non-empty `filters_tried`) |
| comparison | non-empty axes and ≥2 SKU rows, or `status=no_result` with a reason |
| compliance | ≥1 standards claim **or** non-empty `not_established` |
| solution_advisory | ≥1 catalog_backed or engineering_guidance claim; every recommended slot resolved to a family/SKU or explicitly “no C&S product” |
| all agents except an `overview` brief | any `Finding` of kind `specification` must cite a `SourceRef.sku_code` |

The `overview` carve-out is not a loosened standard, it is the right subject.
"Up to 6300 A in 3 or 4 pole" is published on the *Air Circuit Breakers category
page*, so it describes the range and there is no ordering code to attribute it
to. Holding an overview to the SKU rule made the check unsatisfiable by
construction — the depth forbids reaching a SKU, and the rule demands one — so
every overview that quoted a rating failed and re-ran. Category-level facts
belong to `kind: catalogue`; `specification` means a value read against one
`sku_code`.

On failure, the gate may **re-Send only the failing agents once**, appending the
violations as a `revision_note` on their briefs. A retry **resumes on the
specialist's own transcript**: `_run_specialist` keeps each finished message
list in `AgentState.transcripts`, `_send(..., resume=True)` hands it back, and
`prepare` re-enters with it plus the revision note. Because the retrieval is
already there, the retry is capped at `revision_tool_budget` rather than the
full per-agent budget, and its first turn is a KV-cache hit rather than a cold
read of the history.

This is a latency fix. A gate failure is nearly always about the *shape* of the
report — a missing citation, an absent follow-up question — and restarting the
specialist empty made it re-run every tool call to fix a field: one such retry
measured 471s of a 963s run. Violations are still deduplicated: the note is
prose the model reads, and one rule repeated four times reads as four faults.
Retries are counted per stage in `gate_retries`, so a stage that struggled does
not consume the retry another stage may need. This is what keeps weaker local models from “browsing forever
and never looking up a SKU.”

If contracts pass — or the stage's retry is spent — routing moves to the next
stage, and to the composer once none remain. An unfixable stage does not stall
the pipeline: the next stage still runs, and sees the partial report.

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
  `multiple_variants`, and disclose `price_sibling_code` alongside any figure
  carrying it

**How it should read.** The reports are a pipeline artefact; the answer is a
person. Two habits made it read like a query result instead, and the prompt now
forbids both:

- *Two sections.* The prompt used to require a labelled split — catalogue facts
  in one block, general engineering knowledge in another — and the advisory
  report's `catalog_backed` / `engineering_guidance` fields invited the same
  shape. That field boundary exists so a **specialist** keeps its sourcing
  straight; it is not a layout for the customer. The answer is one voice, and
  what separates a retrieved figure from a judgement is wording, not a heading:
  the figure is stated flatly and cited, the judgement is voiced as judgement.
  Honest, and invisible.
- *A gap inventory.* Specialists record every gap they hit, and the composer
  used to surface all of them. Silence is now the default. A gap is mentioned
  only when the customer explicitly asked for that thing, or when acting on the
  answer without it would be a mistake — one sentence in place, never an
  opening, a closing, or a list. A gap nobody asked about makes a complete
  answer read as a failed one.

The same rule covers a family whose `description` is null: write the name and
the SKU count and move on. Inventing a characterisation is the older bug;
announcing the absence is the other half of it, and both are now excluded.

After drafting, the composer **updates session memory** for the next turn:

- append a compact turn summary
- refresh `focus_skus` from cited / candidate / representative codes
- refresh `focus_family` when discovery provided one
- store `prior_reports`

The draft is what the CLI prints, unless `compose_final` already streamed it —
`llm/streaming.py` prints tokens as they arrive and reports back whether it
did, so the CLI does not print the answer twice. The numeric validator node
still exists in the package but is **not wired** into the graph.

### 4.10 Out of scope

When the planner sets `scope` to `company` or `unrelated`, routing skips the
whole pipeline and lands on `out_of_scope`: one short generation, no specialist,
no tool call, no gate, no sufficiency pass. Measured at 9s end to end against
roughly two minutes for the cheapest real catalogue answer.

The two branches are deliberately shaped differently:

- **`company`** — acknowledge what they asked, hand over both the website and
  the phone number **plainly**, and offer catalogue help. No description of what
  is at either destination: the model does not know whether a role is listed or
  whether that page tracks orders, and an early version confidently sent people
  to "browse current openings".
- **`unrelated`** — decline in a line, say what the desk does cover, and where
  there is a plausible product question next to what they asked, offer it. The
  contact details are deliberately **withheld** here; quoting a company hotline
  at a question that has nothing to do with C&S reads as a brush-off.

Contact details live in `config/contact.yaml`, not in the prompt, because the
routing is expected to become per-enquiry — careers, orders, service, dealer
appointment each to their own destination. Adding those means adding keys.
`config/contact.py` loads and caches the file, and `CS_CONTACT_WEBSITE` /
`CS_CONTACT_PHONE` override it for a run without editing a tracked file. The
node substitutes both into `prompts/out_of_scope.md`, so a changed destination
never means a changed prompt.

The reply streams like the final answer, since it *is* the final answer for that
turn.

The turn is recorded in `session.turns` with `out_of_scope` set and no agents,
so a follow-up ("what about a sales role?") still has something to resolve
against.

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
- `SqliteSaver` persists graph state across process restarts.
- The CLI also passes the previous `session` dict into the next
  `run_question()` so follow-ups work even when starting a fresh invoke with a
  reset reports map.

### 5.3 What each layer sees

| Layer | Sees |
|---|---|
| Intake | Raw user message + full session JSON |
| Planner / clarify / specialists / composer | Standalone question, including clarification answers on `session.resolved_params` and dispatch briefs (+ reports as appropriate) |
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
price caveats, taxonomy rules, and the instruction to build on upstream findings
rather than re-retrieve them). Role bodies add method, boundary, and report
shape — each says what it does **and** what it must leave to another stage,
because an agent that quietly widens its scope is what made the old parallel
fan-out duplicate work.

| Specialist | Job | Leaves to others | Typical tools |
|---|---|---|---|
| **discovery** | Map what C&S sells in an area; segment-led entry when the ask is vague; return families + representative SKUs | Filtering to a requirement, ranking, comparing, recommending | taxonomy_browse, product_search, get_peer_group, search_documents |
| **spec_selection** | Name the criticals still missing, then a ranked shortlist meeting them | Finding the families (upstream), designing a wider scheme | list_canonical_specs, product_search, get_sku, get_price_detail, analytics_query |
| **solution_advisory** | Decide the functions a scheme needs and resolve each to a family/SKU | Exhaustive rating filters inside one category | taxonomy_browse, product_search, search_documents, get_sku |
| **comparison** | Side-by-side table; prefer catalogue `comparable_on` when peers match | Finding the codes (upstream), picking a winner | resolve_product, get_peer_group, compare_skus, get_price_detail |
| **compliance** | Published standards / type tests / certifications / manuals only | Selecting or ranking products, inferring conformity from class | list_canonical_specs (topic search), get_sku, search_documents (`standards`) |

Shared tools bound to every specialist: `resolve_product`, `product_search`,
`get_sku`.

Reports are role-specific Pydantic models in `contracts.py`. The gate and
composer both depend on those shapes.

---

## 7. Tools and how they work

Tools are LangChain structured tools. Thin wrappers in `tools/impl.py` call a
`CatalogBackend`. Default production path is `SqliteBackend` over the built
`artifacts/catalog-latest.sqlite` artifact (`sku_fact` + `chunk`). Offline
tests use `FixturesBackend`.

### 7.1 Agent ↔ tool matrix

| Tool | discovery | spec_sel | advisory | comparison | compliance |
|---|:--:|:--:|:--:|:--:|:--:|
| resolve_product | ● | ● | ● | ● | ● |
| product_search | ● | ● | ● | ● | ● |
| get_sku | ● | ● | ● | ● | ● |
| catalogue_map | ● | ● | ○ | ○ | ○ |
| taxonomy_browse | ● | ● | ● | ○ | ○ |
| list_canonical_specs | ○ | ● | ● | ● | ● |
| search_documents | ● | ○ | ● | ○ | ● |
| get_price_detail | ○ | ● | ○ | ● | — |
| compare_skus | — | ○ | — | ● | — |
| get_peer_group | ● | ○ | — | ● | — |
| analytics_query | — | ● | — | ● | — |

● primary / always bound · ○ available · — not bound

### 7.2 Individual tools

**`catalogue_map`**
Fuzzy-matches a phrase against every populated branch of the taxonomy and
returns one row per family in a single call. It answers "where does this live",
which is the question most turns open with.

Each row is broken down by the level columns themselves — `division`,
`product_group`, `product_subgroup`, `product_range` — plus `family`, the SKU
count, the published description, the URL and the market segments. A level the
branch never reaches is omitted rather than returned as the build's `N/A`
padding, so a depth-2 branch carries two level keys and an unplaced one carries
none. The same values also come back as a `path` list, because that is the
argument `taxonomy_browse` and `product_search` take.

It exists because that question used to cost a walk. "What wintrip products do
you have" ran `product_search(text="Wintrip")` (nothing — Wintrip is a family
name, not indexed text), then `taxonomy_browse(path=[])`, then a browse into the
division, then one into the group: four calls and 19,958 prompt tokens to learn
what one column already held. It is now one call and 8,190.

Design notes, each from the data rather than from taste:

- **Matching runs in Python, not SQL.** Labels carry an en dash in `ACB –
  AH-AHA` and a curly apostrophe in `WiNtrip ‘S’ Modular MCB`; a `LIKE` misses
  both. `backends/matching.py` folds them, and the corpus is 56 published paths
  plus a handful of unplaced families, so a full scan is free.
- **Grouped on the level columns, not on `path_text`.** Those columns are what
  the rest of the toolchain consumes, so grouping on the rendered string and
  splitting it back would put a parsed value where the real one was available.
  The two agree exactly on the built catalogue — 66 groups either way, and the
  levels reconstruct every `path_text` — so this is a change of provenance, not
  of result. `family` stays in the group key because it is the only thing
  separating the eleven unplaced branches, which share one all-`N/A` tuple.
- **Counted with `count(DISTINCT sku_code)`.** `sku_fact` is fact-grained —
  256,473 rows for 9,115 SKUs — so a plain `count(*)` would overstate every
  family by a factor of 28.
- **Neither filter is a schema error, not an empty search.** Unfiltered it would
  return the whole taxonomy, which is what `taxonomy_browse` already does, level
  by level and more usefully. The `model_validator` message names both filters
  and points at `taxonomy_browse`, and `handle_tool_errors` turns it into a tool
  result the model can act on.
- **Unplaced families come back separately.** 388 SKUs — RCBO (69), Power
  Quality Device (83), Automatic Transfer Switch (34) — carry a `family` but no
  path, because the pricelist named them and the published taxonomy never did.
  `taxonomy_browse` cannot reach them at all, and a discovery report had already
  recorded "no dedicated RCBO family was surfaced in the taxonomy" as a gap.
  They return under `uncategorised` with the caveat attached.
- **A miss says what to try.** `closest_paths` scores the query against *family
  names*, squashed to alphanumerics — against the full 96-character path a
  seven-character typo is swamped by text it never mentioned, and the right
  family scored below an unrelated one. Cutoff 75, calibrated on the built
  catalogue: "winbrek" scores 77 on `MCCB – Winbreak`, "distribushion board" 89
  on `Distribution Boards`, and "solar inverter" — which C&S does not make —
  tops out at 72, so it returns no suggestions and says to try `product_search`
  instead. A list of unrelated branches reads as an answer.

**`market_segment` is division-grained.** The tag comes from the source
catalogue and is assigned per division, so `Residential` selects Final
Distribution Products — 9 families, 1,664 SKUs — and nothing else, even though
Circuit Breakers, Fuses and Switches all describe residential use in their own
published text. The tool reports the tag and only the tag; the wording of every
description that mentions it lives in the branch descriptions the tool also
returns. `descriptions.SEGMENT_NOTE` states this on every tool that accepts the
argument, because a tool that does not say so gets called with "Domestic" and
returns nothing.

**`resolve_product`**
Three-stage cascade, stop at first hits:

1. Exact match on normalised codes / aliases (case, spaces, hyphens stripped)
2. Fuzzy match via rapidfuzz `WRatio`
3. Description / family text match, then FTS over chunk content

Returns ranked candidates, `resolution` mode, and an alias note when the user
typed a non-canonical spelling. Always use this before SKU-specific tools when
the user typed a code.

**`taxonomy_browse`**
Walk the 2–4 level catalogue `path` one level at a time. Returns children with
SKU counts, leaf flags, and the published description/URL for each child, plus a
`node` block describing the level you are standing on — both read from the
`taxonomy_level` table built from `taxonomy.levels[]`. `_no_category` children
are returned in a separate **uncategorised** block (pricelist section names, not
published categories). `include_facets` rolls up decoded ordering-code axes over
every SKU in the branch, **at any depth** — including the deepest level, where
there are no children left to list. Browsing alone is never a product answer.

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
Provenance-aware pricing. Surfaces every observation plus `price_status` and
`quotable`. Quoting is false only for `multiple_variants` and for SKUs with no
figure at all. When the pricelist table header names a different ordering code,
the response carries `price_sibling_code` and a `caveat`: the figure is reported
**with** that disclosure rather than withheld, because the header names the
table, not the row. Prices are MRP inclusive of GST.

**`get_peer_group`**
Returns the catalogue peer set, `comparable_on` axes, related codes, and peer
decoded differences. Used for shortlists and like-for-like comparison.

**`compare_skus`**
Side-by-side pivot for 2–10 codes. If they share a peer group, axes default to
the intersection of `comparable_on`; otherwise the union of present specs.
Returns `peer_group_match` and `axes_source`. Empty cells mean not published.

**`search_documents`**
Qualitative retrieval only (features, application, installation, standards
prose). **Requires** a `family`, `path`, or `sku_code` prefilter (enforced in
code). On SQLite:

1. If embeddings are loaded and sqlite-vec is available → embed the query with
   **Alibaba-NLP/gte-base-en-v1.5** (normalized 768-d), rank survivors with
   `vec_distance_cosine`, dedupe by `content_hash`, return `mode: "vector"`.
2. If zero vector hits, embeddings are absent, or sqlite-vec cannot load →
   FTS5 lexical fallback, `mode: "lexical"`.

Never use it for numeric rating lookup.

**`analytics_query`**
Delegates multi-step SQL analysis to a private analytics subgraph
(`prepare → analyst ⇄ execute_analytics_sql → summarize`). The analyst may run
several read-only queries against `sku_fact` / `chunk` (SQLite dialect; capped by
`analytics_max_queries`) and returns a factual summary with numeric evidence —
no recommendations. Used when ranking/aggregating many SKUs is awkward with
the structured tools alone.

One statement per call, and it must read only: `SELECT`, `WITH … SELECT`, or
`VALUES`. `read_only_sql_error` in `cs_agent/backends/read_only_sql.py` is the
single definition, shared by the tool and the fixtures backend so the two cannot
disagree about what a query is. It rejects an internal `;` and a data-modifying
keyword in statement-head position, checked against a copy with string literals
blanked so a `LIKE` pattern is not mistaken for syntax. The SQLite connection
opens `mode=ro`, so this is defence in depth rather than the enforcement; what it
buys is a specific message — a rejection that names the wrong fault costs a query
from the budget and gets the same SQL sent again.

`prepare` seeds the SQL writer with a specification vocabulary. That registry is
one row per `(family, spec_id)` — 1,712 rows, ~108k tokens — so it is scoped
before injection: to the caller's `family` when one is supplied, then cut to
`analytics_registry_chars` keeping canonical specs first and the widest-coverage
specs after. The prompt states how many rows of how many are shown and how to
find the rest, because the analyst has SQL and can discover any spec it needs.

### 7.3 Tool result size

Every tool result becomes prompt tokens on the next turn. Measured on the
2026-08-16 catalogue against the `num_ctx: 80000` the local profiles ran at the
time, four payloads could each fill that window on their own:

| Payload | Before | After | Cap |
|---|---:|---:|---|
| Analytics spec registry (per call) | ~107,700 tok | ~6,000 tok | `analytics_registry_chars` |
| `get_peer_group` (1,183-member group) | ~61,300 tok | ~2,400 tok | `max_peer_rows` |
| `taxonomy_browse` at root with facets | ~28,300 tok | ~2,300 tok | `max_facet_rows` |
| `search_documents` k=5 | ~9,300 tok | ~2,400 tok | `max_chunk_chars` |
| `get_sku` with chunks and peers | ~76,400 tok | ~13,500 tok | the three above |

Every cap is a **page, not a filter**. Each truncated result carries the true
total (`peer_count`, `facet_axis_value_count`) and a note naming the tool that
reaches what was left out, so a capped list is never read as an exhaustive one —
"C&S does not make that variant" must never be an artefact of a cap.

### 7.4 Context-window overflow

Ollama does not reject a prompt larger than `num_ctx`; it drops the overflow and
answers anyway, and what it drops is the head — system prompt, brief, tool
schemas. The model then invents tool names and ignores the report contract, and
the run reads as a model-quality problem rather than a truncated prompt.

`llm/context_guard.py` makes it visible, hooking `ChatOllama._chat_params` so it
measures the assembled request body (converted messages **and** bound tool
schemas), and emits to the trace:

| Event | Meaning |
|---|---|
| `llm.context_pressure` | Estimated prompt is within 85% of the usable window |
| `llm.context_overflow` | Estimated prompt exceeds `num_ctx − num_predict` |
| `llm.prompt_truncated` | Ollama reported `prompt_eval_count` at the window size — confirmed, not estimated |

The estimate divides characters by `CS_CHARS_PER_TOKEN` (default 3.5, below the
usual English figure because catalogue JSON tokenizes worse than prose; for a
warning, over-estimating is the safe direction). These three events print to the
terminal even though other `llm.*` events are suppressed. A *low*
`prompt_eval_count` proves nothing — prefix-cache hits are not re-evaluated —
which is why the pre-flight estimate exists alongside it.

### 7.5 Tool failure behaviour

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
projects eight views used as the **build source** for the SQLite artifact:

| View | Role |
|---|---|
| `mv_sku` | One row per product: path, aliases, peers, extraction, price observations |
| `mv_code_alias` | sku / canonical / alias resolution surface |
| `mv_fact` | Long typed facts with range + composite support |
| `mv_price` | Price observations + pricelist-header sibling-code detector |
| `mv_source` | Typed citation refs (brochure `.md`, product page, pricelist PDF+page) |
| `mv_spec_registry` | Per-family spec vocabulary + observed bounds |
| `mv_facet` | Ordering-code facet axes per family |
| `mv_chunk_index` | Cheap “does this SKU have chunk_type X?” lookups |

Refresh order matters (`mv_sku` first). Use
`python -m cs_agent.db.refresh setup|refresh|inspect`.

### 8.3 Runtime SQLite artifact

`scripts/build_sqlite.py` flattens the views into one read-only file.
Column-level detail and the current build snapshot are in
[`SQLITE-CATALOG.md`](SQLITE-CATALOG.md).

| Table | Grain |
|---|---|
| `sku_fact` | One row per (SKU, fact); SKU metadata repeated; sentinel rows for factless SKUs |
| `taxonomy_level` | One row per catalogue node; published description, URL, leaf flag |
| `chunk` | One row per brochure chunk; embedding as float32 BLOB; FTS5 `chunk_fts` |
| `build_meta` | Build timestamp, counts, embedding dim, audit flags |

Path depth is compiled from live pre-flight (**4** levels today):
`division`, `product_group`, `product_subgroup`, `product_range`, with `'N/A'`
padding. Always filter families on `family`, never on a level column.

Default runtime: `CS_BACKEND=sqlite` → `SqliteBackend` + `SqliteSaver`
(`state/checkpoints.sqlite`). If `sqlite-vec` fails to load, `search_documents`
uses FTS5 lexical search on the same SQLite file.

Factless SKUs are listed in `artifacts/build_report.json` with a warning; the
build exits 0 after emitting sentinel rows.

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

### 8.4 Catalogue semantics the agents must respect

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

- `intake`, `planner`, `clarify`, `composer`, `out_of_scope`
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

### 10.1 Watching a specialist write

Decode is the largest single cost in a turn and the specialist report is most of
it — 1,669 of one overview run's 2,744 output tokens, 46s of decode, for a final
answer of 1,310 characters. Until it finished, none of it was visible.

Three calls now stream to the terminal as they generate:

| Caller | Shown as | Why |
|---|---|---|
| `compose_final`, `out_of_scope` | raw text under `Answer` | it *is* the answer; the terminal wraps it |
| specialist tool loop | `┊ [discovery] …` | the prose it writes between tool calls |
| specialist report node | `┊ [discovery report] …` | the JSON, as it is built |

Each specialist stream closes with what it cost —
`⏹ 1,669 output tokens in 45.8s (36 tok/s)` — because the reason to watch is to
find tokens not worth generating, and that judgement needs the rate as well as
the count.

Specialists fan out in parallel, so a token-level write straight to stdout would
shred five agents' output together. Labelled output is therefore buffered and
emitted as whole lines, broken on a space at 100 columns, through the trace
logger's own lock — so a streamed line can never land inside a progress line.
The answer is written raw instead, because nothing else is competing for the
terminal by then.

A caller whose reply may carry a tool call also passes the names of the tools
bound to the model, so `generate` can notice a mis-parsed tool name and re-run
the turn unstreamed (§4.6).

Everything else — intake, planner, the sufficiency check, analytics — passes no
label and does not stream: short, structured, and only noise on screen. When
nothing is being shown, `generate` falls through to a plain `invoke`, so no
behaviour depends on whether anyone is watching. Silence the specialist streams
alone with `CS_STREAM_AGENTS=false`.

`ContextAwareChatOllama._stream` repeats the truncation check `_generate` does,
because the report is exactly where a silently truncated prompt does the most
damage and it is now on the streaming path.

### 10.2 Where a run's time goes

`latency_profile.py <trace.jsonl>` splits a run into tool execution and model
time, and — on Ollama — uses the server's own counters to break model time into
load, prefill and decode, attributed per pipeline stage.

Two facts shape every optimisation here, and both were surprises:

**Tools are free.** Across a measured two-question session, 60 tool calls took
25.4s against 1,712s of model time — 0.9% of wall clock. Nothing in the
catalogue layer is worth tuning for latency. What costs is tokens through the
model, so the levers are: fewer calls, shorter prompts, fewer generated tokens,
and prompt prefixes the server can reuse.

**Measured effect of the changes above.** The same two questions, same model
(`qwen3.6:27b`), before and after the report node was folded into the
specialist's thread, gate retries were made to resume, repeat tool calls were
suppressed, and the loop was told to stop writing the report in prose:

| | before | after |
|---|---:|---:|
| wall, question 1 | 963s | 450s |
| wall, question 2 (follow-up) | 804s | 623s |
| model prefill | 677s | 232s |
| model decode | 1,002s | 799s |
| tool calls | 60 | 39 |
| output tokens | 11,072 | 9,258 |
| effective prefill | 1,584 tok/s | 3,351 tok/s |

Prefill fell by two thirds; decode by a fifth, and only because fewer tokens
were generated. That ratio is the point: prompt-side work is nearly free to
optimise and nearly exhausted, and what remains is generation.

**Prefill is cheap when cached; decode never is.** A tool-calling loop re-sends
its whole transcript every turn, so `resend` in the profile's prefix-reuse table
is normally several times 1.0. That is inherent and not a problem *if* the
server charges only for the new tokens: cached loop turns measure 6,000–7,800
tok/s against a ~790 tok/s cold rate on the same box. Decode has no such
escape — it runs at whatever the model does, and on qwen3.6:27b that is 11–12
tok/s regardless of context size (measured flat across 4k, 64k, 80k and 131k
windows). Once prefill is cached, decode is 78% of model time, and the only
remaining levers are generating fewer tokens or serving a faster model.

The prefix-reuse verdict compares the aggregate rate against the run's **first**
call, not its quickest. Using the quickest inverts the test: once caching works,
the quickest call is a cache hit, and every healthy run reports as broken.

What a healthy prefix looks like, from one specialist's report call before and
after the tool schemas were kept bound on it:

| | prompt | prefill | rate |
|---|---:|---:|---|
| unbound tools (cold) | 51,011 tok | 72.0s | 708 tok/s |
| bound, first attempt | 40,087 tok | 12.7s | 3,146 tok/s |
| bound, `structured` retry | 40,162 tok | 0.4s | 104,185 tok/s |

The middle row is a wasted attempt: with tools in scope the model sometimes
answers the report request with a tool call instead of JSON, which fails
validation. It costs ~5s of decode and leaves the whole transcript cached, so
the retry that follows prefills in 0.4s — still 87s ahead of the cold path.
That trade is why the tools stay bound despite the occasional wasted call.

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
| `make test` | Every suite: fixtures-only framework tests, then the SQLite and vector suites against the built catalogue |
| `make test-vector` | The vector suite alone; needs the built catalogue with 768-d embeddings loaded |
| `make setup-db` / `make refresh` / `make inspect` | Catalogue projection lifecycle |
| `python -m cs_agent.run …` | Interactive or one-shot answering |

`tests/test_vector_retrieval.py` runs as part of `make test`. Vector retrieval
is a shipped code path and the embeddings are built into the artifact, so a
silent skip would let a regression reach a live run. It defaults to a family
with plenty of embedded `features`, `application` and `installation` chunks;
override with `CS_VECTOR_TEST_FAMILY` if a rebuild changes the catalogue's
shape, and set `CS_SKIP_VECTOR_TESTS=1` only when working without an artifact.

---

## 12. Mental model of one successful answer

1. User asks a follow-up about “that MCCB” on an existing thread.
2. Intake rewrites it to an explicit SKU/family question using session focus.
3. Planner confirms the question is a catalogue one, then orders the work:
   discovery at stage 1, spec_selection at stage 2, and compliance alongside
   spec_selection only if the question asks for standards. (Had it been a job
   application or a lightbulb, the turn would have ended here.)
4. Stage 1 runs. Discovery privately calls structured tools, records evidence,
   and emits a typed report with sources and gaps.
5. Gate bounces a report that browsed families but never produced SKUs or
   reasons; one targeted retry is allowed for that stage.
6. Stage 2 runs with discovery's digest on its opening turn, so spec_selection
   filters inside the families already found instead of re-walking the taxonomy.
7. Composer checks sufficiency; if a standards claim is still missing it
   re-sends only compliance with that gap.
8. Final answer is written from the reports, citations included, session
   updated for the next turn.

That separation — **rewrite → plan an order → retrieve stage by stage →
structurally check → revise narrowly → compose from reports** — is the core of
the v2 architecture.
