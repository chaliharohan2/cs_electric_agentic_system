# C&S Product Agent — Implementation Plan (POC v1)

**Stack:** LangChain + LangGraph · Python 3.11+ · Postgres 17 + pgvector · one OpenAI-compatible wire format for all models

**Out of scope for v1:** ingestion, compatibility checking, asset retrieval, SQL guardrails, personas, multi-domain routing, config assembler.

**Deferred inputs:** DB schema (tools run against a swappable backend; fixtures backend works today), eval dataset.

---

## 1. Verified model facts

Both target open models: <cite index="3-1,4-1">Qwen3.6-27B and Qwen3.6-35B-A3B have a default context length of 262,144 tokens, natively supported and extensible to ~1,010,000 tokens</cite>. **No context-budgeting machinery is needed** — evidence is passed to nodes in full.

Tool calling on vLLM: serve with `--enable-auto-tool-choice --tool-call-parser qwen3_xml`. <cite index="16-1">The vLLM recipe for Qwen3.6-27B uses `--tool-call-parser qwen3_xml --enable-auto-tool-choice` together with `--reasoning-parser qwen3`</cite>, and <cite index="12-1">`qwen3_xml` is the more advanced parser for Qwen3 models</cite>. <cite index="13-1">vLLM's tool-calling documentation covers parallel tool calls across its model-specific parsers</cite> — treat this as available but verify on your own serving stack, since it is a serving-config property, not a model property. The code path works either way.

`--reasoning-parser qwen3` places thinking tokens in a separate `reasoning_content` field rather than in `content`. `ChatOpenAI` reads `content`, so thinking is dropped automatically; it surfaces in `response_metadata` if you want to log it.

Anthropic side: <cite index="25-1">the Claude API accepts OpenAI-format requests at `https://api.anthropic.com/v1/` using the Claude model name and the Anthropic key</cite>. Two caveats: <cite index="25-1">the `strict` parameter for function calling is ignored, so tool-use JSON is not guaranteed to match the supplied schema, and prompt caching is not available on this path</cite>.

**Consequence:** a single `ChatOpenAI` class, pointed at different `base_url`s, covers Sonnet and both Qwen models. Switching models is a config edit, and LangChain is retained. The `strict`-ignored caveat means structured output needs validate-then-retry regardless of provider — build it once (§3.3).

---

## 2. Repository layout

```
cs_agent/
  config/
    endpoints.yaml         # THE swap point
  llm/
    factory.py             # get_model(node) -> ChatOpenAI
    structured.py          # structured(node, messages, schema) with retry
  graph/
    state.py
    build.py
    nodes/
      planner.py  clarify.py  agent.py  record_evidence.py
      composer.py  validator.py
  subgraphs/analytics/
    build.py  nodes.py  tool.py
  tools/
    schemas.py             # pydantic args schemas
    descriptions.py        # tool description strings (§6)
    impl.py                # callables -> backend
    registry.py            # TOOLS: list[StructuredTool]
  backends/
    protocol.py  fixtures.py  postgres.py
  validation/numeric_fidelity.py
  prompts/                 # one .md per node (§7)
  run.py                   # CLI
```

**Why LangChain stays:** `ToolNode` and `add_messages` remove the tool-call plumbing entirely; `StructuredTool` derives tool JSON schemas from Pydantic so the schema and the Python signature cannot drift; and pgvector retrievers, callbacks, and LangSmith tracing all plug in without adapters once ingestion lands.

---

## 3. Model layer

### 3.1 `config/endpoints.yaml`

```yaml
endpoints:
  sonnet:
    base_url: https://api.anthropic.com/v1/
    model: claude-sonnet-5
    api_key_env: ANTHROPIC_API_KEY
    temperature: 0.0
    max_tokens: 4096

  qwen_a3b:
    base_url: http://10.0.0.11:8000/v1
    model: Qwen/Qwen3.6-35B-A3B
    api_key_env: LOCAL_LLM_API_KEY
    temperature: 0.0
    max_tokens: 4096
    extra_body:
      chat_template_kwargs: {enable_thinking: false}

  qwen_27b:
    base_url: http://10.0.0.12:8000/v1
    model: Qwen/Qwen3.6-27B
    api_key_env: LOCAL_LLM_API_KEY
    temperature: 0.6          # Qwen thinking mode prefers non-zero
    max_tokens: 8192
    extra_body:
      chat_template_kwargs: {enable_thinking: true}

# ---- switching models = editing this block only ----
nodes:
  planner:   sonnet
  clarify:   sonnet
  agent:     sonnet
  composer:  sonnet
  analytics.write_sql: sonnet
  analytics.shape:     sonnet
```

Override without editing the file: `CS_MODELS=all:qwen_27b` or `CS_MODELS=agent:qwen_a3b,composer:qwen_27b`.

Later target (benchmark first): `agent`, `clarify`, `analytics.shape` → `qwen_a3b`; `planner`, `composer`, `analytics.write_sql` → `qwen_27b`.

### 3.2 `llm/factory.py`

```python
@lru_cache(maxsize=None)
def get_model(node: str) -> ChatOpenAI:
    ep = resolve_endpoint(node)            # yaml + CS_MODELS override
    return ChatOpenAI(
        model=ep.model,
        base_url=ep.base_url,
        api_key=os.environ[ep.api_key_env],
        temperature=ep.temperature,
        max_tokens=ep.max_tokens,
        extra_body=ep.extra_body or {},
        timeout=ep.timeout,
        max_retries=3,
    )
```

That is the whole model layer. One class for all three models, because Anthropic and vLLM both speak OpenAI chat completions. No node imports `ChatOpenAI` directly — always `get_model(node)`.

*Escape hatch, if ever needed:* if you later want native Anthropic features (prompt caching, extended thinking), that requires `ChatAnthropic` and breaks the single-class property. Not needed for the POC; note it as the one thing that would force a second code path.

### 3.3 `llm/structured.py`

```python
def structured(node: str, messages: list, schema: type[BaseModel], attempts: int = 2):
    model = get_model(node)
    msgs = list(messages)
    for _ in range(attempts + 1):
        raw = model.invoke(msgs).content
        try:
            return schema.model_validate_json(strip_fences(raw))
        except ValidationError as e:
            msgs += [AIMessage(content=raw),
                     HumanMessage(content=f"Invalid output. Fix these errors:\n{e}")]
    raise StructuredOutputError(node)
```

Prompted JSON plus explicit retry, rather than `with_structured_output`. Reason: the schema-conformance guarantee differs across the two providers (`strict` is ignored on the Anthropic path), so the retry loop is required anyway — and this behaves identically everywhere, which is the point of the whole design. The schema is injected into the system prompt via `schema.model_json_schema()`.

---

## 4. State

```python
class Evidence(TypedDict):
    tool: str
    family_id: str | None
    canonical_fact_id: str | None
    value_num: float | None
    value_text: str | None
    unit: str | None
    conditions: dict           # {"voltage_v": 415, "poles": 3}
    doc: str | None
    page: int | None

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: dict | None
    evidence: Annotated[list[Evidence], operator.add]
    clarify_count: int          # HARD CAP 2
    tool_calls_made: int        # HARD CAP 12
    assumptions: list[str]
    draft: str | None
    validation: dict | None
```

`evidence` is append-only and is the only source the composer may use for
catalogue claims.

---

## 5. Graph

```
START → planner
          ├ needs_clarification and clarify_count < 2 → clarify → planner
          └ otherwise                                          → agent
agent → tools (ToolNode) → record_evidence → agent   [until no tool_calls or budget hit]
      → composer → END
```

Checkpointer: `PostgresSaver` (`MemorySaver` in tests) — required for `interrupt()`.

**planner** — `structured()` → `Plan{intent, categories[], target_facts[], known_params, open_params[], needs_clarification, strategy}`. Merges clarify answers on re-entry.

**clarify** — `interrupt()`, up to 3 questions. `clarify_count` incremented here; the cap is enforced in the **conditional edge**, not the prompt, so no model can talk past it. On cap, remaining `open_params` become `assumptions` and the run continues.

**agent** — `get_model("agent").bind_tools(TOOLS).invoke(messages)`. Conditional edge: `tool_calls` present and budget remaining → `tools`; otherwise → `composer`.

**tools** — `ToolNode(TOOLS)`. Handles parallel calls, error wrapping, and `ToolMessage` construction for free.

**record_evidence** — reads `ToolMessage`s added since the last visit, parses each into `Evidence` records with a per-tool parser (plain Python, no LLM), increments `tool_calls_made`. Kept as a separate node rather than folded into custom tool code so `ToolNode` stays stock.

**composer / validator** — §7.4 and §8.

**Dropped from the earlier draft:** `config_assembler`. Without `get_compatibility` it can only restate what the agent already retrieved. Its one real job — attaching the "compatibility not verified" caveat to multi-component recommendations — moves into the composer prompt. Reintroduce it when the compatibility tool lands.

---

## 6. Tools

Built with `StructuredTool.from_function(func, args_schema=..., description=...)` so the JSON schema is generated from Pydantic and cannot drift from the Python signature.

Descriptions live in `tools/descriptions.py`. **Ship them as written below** — they are the only thing steering tool choice, and each names the specific failure it prevents.

```python
# tools/schemas.py
class FactFilter(BaseModel):
    canonical_fact_id: str
    op: Literal["eq","gte","lte","in","contains"]
    value: Any
    conditions: dict | None = Field(None,
        description='e.g. {"voltage_v": 415, "poles": 3}. Required when the fact '
                    'declares condition_keys.')

class ProductSearchArgs(BaseModel):
    category_path: str
    filters: list[FactFilter] = []
    text: str | None = Field(None, description="Optional free-text name/code match.")
    limit: int = 20

class GetProductArgs(BaseModel):
    family_id: str
    fact_groups: list[Literal["electrical","mechanical","dimensions","certifications",
                              "trip_units","accessories","commercial"]]
    include_variants: bool = False

class SearchDocumentsArgs(BaseModel):
    query: str
    category_path: str | None = None
    family_id: str | None = None
    k: int = 6

class TaxonomyBrowseArgs(BaseModel):
    node_id: str | None = Field(None, description="Category node. Omit for the root.")
    depth: int = Field(1, description="Levels to expand, 1-2.")

class ListCanonicalFactsArgs(BaseModel):
    category_path: str | None = Field(None,
        description="Taxonomy path, e.g. 'protection/mccb'. Omit for all categories.")

class AnalyticsQueryArgs(BaseModel):
    question: str
    scope: dict | None = Field(None,
        description="family_ids[] or a category_path to bound the query.")
    output_shape: str = Field(...,
        description="e.g. 'one row per family, columns: code, In, Icu@415V, price'")
```

```python
# tools/descriptions.py

LIST_CANONICAL_FACTS = (
    "List the canonical fact IDs available for a product category, with their units, "
    "value types, and the condition keys they require. "
    "ALWAYS call this before using product_search filters in a category you have not "
    "queried yet in this conversation. Fact IDs are exact strings — guessing them "
    "(e.g. 'breaking_capacity' instead of 'icu_ka') returns nothing, and you will "
    "wrongly conclude the product does not exist."
)

TAXONOMY_BROWSE = (
    "Browse the C&S product taxonomy one level at a time. Returns child categories "
    "each with a product_count. Use this to find what C&S actually sells before "
    "searching, and to tell 'no such product exists' apart from 'my filter was wrong' "
    "— a category with product_count > 0 that returns no search hits means the filter "
    "is wrong, not that the range is empty."
)

PRODUCT_SEARCH = (
    "Find product families by structured attribute filters. This is the PRIMARY tool "
    "for any question involving a number, a rating, a range, or a superlative "
    "(cheapest, highest, smallest). Do not use document search for those. "
    "Filters use exact canonical_fact_id values from list_canonical_facts. "
    "If a fact requires conditions (e.g. breaking capacity depends on voltage) you "
    "MUST supply them — the same breaker can be rated 200 kA at 240 V and 20 kA at "
    "690 V, so an unconditioned filter is meaningless and will be rejected."
)

GET_PRODUCT = (
    "Full detail for one product family: facts grouped by area, plus variants if "
    "requested. Request only the fact_groups you need — asking for all of them returns "
    "a large payload that makes the rest of the task harder. Use after product_search "
    "or taxonomy_browse has identified a family_id."
)

SEARCH_DOCUMENTS = (
    "Semantic search over brochure text. Use ONLY for qualitative questions: how a "
    "feature works, what an application note says, whether a product suits a use case, "
    "what a standard requires. Never use it to find, rank, or compare numeric ratings "
    "— embeddings cannot distinguish 30 A from 40 A, or TCDP301 from TCDP302. Always "
    "pass a category_path or family_id filter; unfiltered search across 500 brochures "
    "returns noise."
)

ANALYTICS_QUERY = (
    "Run a free-form analytical query across many products — cross-family comparisons, "
    "rankings, aggregates, or anything needing a pivot. Returns a result table only, "
    "with no interpretation. Use when the answer is a table over several products "
    "rather than a lookup on one. State the question in plain language and the shape "
    "of table you want back."
)
```

`get_compatibility` and `get_assets` are **not registered**. Add them when implemented; an unregistered tool cannot burn budget on failed calls.

### 6.1 Backend

```python
class CatalogBackend(Protocol):
    def list_canonical_facts(self, category_path: str | None) -> list[dict]: ...
    def taxonomy_browse(self, node_id: str | None, depth: int) -> dict: ...
    def product_search(self, **kw) -> list[dict]: ...
    def get_product(self, family_id: str, fact_groups: list[str],
                    include_variants: bool) -> dict: ...
    def search_documents(self, **kw) -> list[dict]: ...
    def execute_sql(self, sql: str) -> dict: ...
```

`FixturesBackend` reads JSON hand-built from the DP-Contactor and WiNbreak2 brochures — **build this first**; it makes the graph runnable before the DB exists. `PostgresBackend` methods each `raise NotImplementedError("SCHEMA_PENDING")` with a docstring stating the required return shape. Selected by `CS_BACKEND=fixtures|postgres`.

One piece of tool-layer logic to implement now, independent of schema: `product_search` must reject a filter on a condition-bearing fact when `conditions` is missing, returning `{"error": "...requires conditions: [voltage_v]"}` rather than results.

---

## 7. Prompts

One file per node in `prompts/`. Ship as written; refine after the first eval run.

### 7.1 `prompts/planner.md`

```
You plan how to answer questions about C&S Electric's product catalogue.

Classify the question into exactly one intent:
- lookup   : facts about one known product
- compare  : several named or filterable products against shared criteria
- select   : "which product should I use for X" — needs a recommendation
- explain  : how something works, or general electrical guidance

Then produce a plan. Rules:

1. Name the taxonomy categories in scope. If unsure, leave empty — the agent will
   browse the taxonomy.
2. List the canonical facts likely needed. Use plain names; exact IDs are looked up later.
3. Put every parameter the user gave into known_params.
4. Put missing parameters into open_params.
5. Set needs_clarification TRUE only if a missing parameter would change WHICH PRODUCT
   FAMILY is recommended. Load current, voltage system, application type, and
   installation environment qualify. Coil frequency, mounting style, and terminal type
   do NOT — those are variants, and the answer can simply cover both.
6. Never ask for something the user already stated.

Reply with ONLY the JSON object.
```

### 7.2 `prompts/clarify.md`

```
Ask at most 3 questions to fill the open parameters. Each question must:
- be answerable in one short line by an electrical contractor or panel builder
- include a suggested default in parentheses so the user can skip it
- avoid jargon the user has not already used

Do not explain why you are asking. Do not preface with pleasantries.
Output the questions as a numbered list and nothing else.
```

### 7.3 `prompts/agent.md` (system message)

```
You answer questions about C&S Electric products using the provided tools.

Tool discipline:
- Anything involving a number, rating, range, or superlative → product_search
  (after list_canonical_facts for that category).
- Qualitative or "how does it work" → search_documents.
- Tables across many products → analytics_query.
- Never state a specification you did not retrieve from a tool.

Sequencing: taxonomy_browse to find the category → list_canonical_facts to learn the
fact IDs → product_search to shortlist → get_product for detail. Skip steps you
already have results for. Call tools in parallel when they are independent.

Conditions are not optional. Ratings in this catalogue depend on voltage, pole count,
and ambient temperature. Always carry the conditions with the value.

If a tool returns an error naming required conditions, add them and retry — do not
switch to document search to work around it.

If the catalogue does not cover something, say so plainly. Do not substitute a
different product silently.

Stop calling tools once you have what the plan asked for.

Plan for this question:
{plan_json}
```

### 7.4 `prompts/composer.md`

```
Write the answer using ONLY the evidence below.

Evidence (every retrieved fact, with source):
{evidence_table}

Assumptions made because the user did not specify:
{assumptions}

Rules:
1. Every specification you state must appear in the evidence table. If it is not there,
   either omit it or mark it clearly as general engineering practice rather than a C&S
   specification.
2. State the conditions with every conditional value: "Icu 150 kA at 415 V", never
   "Icu 150 kA".
3. Cite as: product code (document, page).
4. Separate catalogue facts from general engineering knowledge. Use two clearly
   labelled sections when the answer contains both.
5. Open by listing the assumptions you worked from, if any.
6. If you recommend a configuration with more than one component (breaker plus trip
   unit, contactor plus accessory), add: "Component compatibility has not been verified
   against the accessory matrix — confirm with C&S before ordering."
7. If the catalogue does not cover part of the question, say which part.
8. Neutral, professional tone. No sales language.
```

### 7.5 `prompts/analytics_write_sql.md`

```
Write ONE PostgreSQL SELECT statement answering the question below.

Schema:
{schema_ddl}

Canonical facts in scope:
{fact_registry}

Rules:
- One statement, SELECT only.
- Facts that carry conditions must be filtered on those conditions, or the comparison
  is meaningless.
- Handle NULLs explicitly when ranking; a missing fact is not a zero.
- Return the columns requested in output_shape, using those names.

Output only the SQL. No explanation, no fences.
```

### 7.6 `prompts/analytics_shape.md`

```
Turn this result set into the requested output shape.
Write a one-line note stating what was excluded and why (e.g. rows dropped for missing
facts). Do NOT interpret, rank by judgement, or recommend anything.
```

---

## 8. Numeric fidelity validator (dormant)

Deterministic, no LLM. `validation/numeric_fidelity.py`.

1. Strip product codes and standard references from the draft **first** (`CS250`, `TCDP202`, `ETM43`, `IEC 60947-2`). Skipping this makes the `250` in `CS250` fail on every MCCB answer.
2. Extract remaining `(number, unit, span)` triples.
3. Exclude numbers present verbatim in the user's message, list ordinals, and years.
4. Match each against `Evidence.value_num` (unit-normalised, rel-tol 1e-6) or `value_text`.
5. Assert that any matched fact with non-empty `conditions` has those conditions stated in the same sentence.
6. Unmatched → `fail` with the offending spans.

Dormant routing behavior if re-enabled: first failure → composer with the spans
listed. Second → strip those sentences and append *"Some figures could not be
verified against the catalogue and were removed."*

The implementation is retained for future evaluation, but it is not registered
in the active graph. The composer routes directly to `END`.

Report `numbers_total / matched / unmatched[]` to the trace. This is the headline metric when comparing Sonnet against the Qwen profiles.

---

## 9. Build order

| # | Step | Done when |
|---|---|---|
| 1 | `llm/factory.py` + `endpoints.yaml` | Same `get_model()` reaches Anthropic and a local vLLM; `bind_tools` round-trips on both |
| 2 | Tool schemas, descriptions, `FixturesBackend` | Tools invokable from a REPL against fixture data |
| 3 | State + evidence parsers | `ToolMessage` output becomes Evidence with no LLM involved |
| 4 | `agent` + `ToolNode` + `record_evidence` + `composer` | End-to-end answer on 5 fixture questions |
| 5 | Numeric fidelity validator | An injected wrong figure is caught and removed |
| 6 | `planner` + `clarify` (cap 2) | Vague question triggers one clarify round, then proceeds |
| 7 | Analytics subgraph | Cross-family comparison returns a correct table |
| 8 | `PostgresBackend` | Schema arrives; only this file changes |
| 9 | Eval harness | Metrics per endpoint profile |
| 10 | Model swap | `endpoints.yaml` edit only |

Steps 1–6 are demoable to C&S on fixtures alone.

---

## 10. Questions for the coding model when the schema lands

1. Family/variant split — is `include_variants` real or a no-op?
2. Are conditions a JSONB column or normalised columns? Determines filter translation.
3. Absence semantics — the MCCB tables use `-`, `●`, `▲`, and blank for four different meanings (not applicable, available, optional, not stated). They must not collapse to NULL.
4. Is the canonical fact registry queryable, or does `list_canonical_facts` read a static file?
5. Embedding model and vector column name for `search_documents`.
