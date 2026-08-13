# C&S Product Agent — Implementation Plan (POC v1)

Single source of truth. Supersedes all earlier drafts.

**Stack:** LangChain + LangGraph · Python 3.11+ · Postgres 17 + pgvector · one OpenAI-compatible wire format for all models

**In scope:** a single agent answering product questions over the existing `in_use.product_chunks` table — lookup, comparison, selection, and explanation.

**Out of scope for v1:** ingestion, compatibility checking, asset/curve retrieval, SQL guardrails, user personas, multi-domain routing (FAQ, pricing), config assembly.

**Handled outside this plan:** embedding model configuration and the query-side embedding call. Tools assume an `embed(text) -> list[float]` function is provided and matches ingestion.

---

## 1. Model layer

Both target open models have a <cite index="3-1">default context length of 262,144 tokens, natively supported</cite>, so no context-budgeting machinery is required — evidence is passed to nodes in full.

vLLM serving: `--enable-auto-tool-choice --tool-call-parser qwen3_xml --reasoning-parser qwen3`. <cite index="16-1">This is the published vLLM recipe for Qwen3.6-27B</cite>, and <cite index="12-1">`qwen3_xml` is the more advanced parser for Qwen3 models</cite>. <cite index="13-1">vLLM documents parallel tool calls across its model-specific parsers</cite> — treat as available, verify on your stack; the code path works either way. `--reasoning-parser qwen3` places thinking tokens in `reasoning_content`, which `ChatOpenAI` ignores automatically.

Anthropic: <cite index="25-1">the Claude API accepts OpenAI-format requests at `https://api.anthropic.com/v1/` using the Claude model name and the Anthropic key</cite>. Caveats: <cite index="25-1">the `strict` parameter for function calling is ignored, so tool-use JSON is not guaranteed to match the supplied schema, and prompt caching is unavailable on this path</cite>.

**Consequence:** one `ChatOpenAI` class pointed at different `base_url`s covers all three models. Switching models is a config edit.

### 1.1 `config/endpoints.yaml`

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

Override without editing: `CS_MODELS=all:qwen_27b` or `CS_MODELS=agent:qwen_a3b,composer:qwen_27b`.

Later target (benchmark before committing): `agent`, `clarify`, `analytics.shape` → `qwen_a3b`; `planner`, `composer`, `analytics.write_sql` → `qwen_27b`.

### 1.2 `llm/factory.py`

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

No node imports `ChatOpenAI` directly — always `get_model(node)`.

*Known limitation:* native Anthropic features (prompt caching, extended thinking) would require `ChatAnthropic` and a second code path. Not needed for the POC.

### 1.3 `llm/structured.py`

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

Prompted JSON with explicit retry rather than `with_structured_output`, because schema conformance differs across providers (`strict` is ignored on the Anthropic path) — the retry is required anyway, and this behaves identically everywhere. Inject `schema.model_json_schema()` into the system prompt.

---

## 2. Data layer

### 2.1 Why derived views

`in_use.product_chunks` is chunk-grained and fully denormalised — `taxonomy`, `product`, and `details` are byte-identical across all ~11 chunks of a SKU. Querying it directly means every tool starts with de-duplication, and the GIN `jsonb_path_ops` index on `details` serves containment only, not the numeric range filters product search is built on.

Four materialised views, refreshed after each wholesale reload. Tools read only these. `product_chunks` remains source of truth and vector index. This also transforms the analytics sub-agent's odds of writing correct SQL — flat columns instead of `jsonb_path_query` over a nested array.

**Identifier policy:** `sku_code` is unique catalogue-wide and is the sole product identifier exposed to the agent. `product_id` is internal — kept in views for join efficiency, never returned by a tool, never in evidence.

### 2.2 Helper

```sql
CREATE FUNCTION in_use.safe_num(t text) RETURNS double precision
LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN t ~ '^-?[0-9]+(\.[0-9]+)?$' THEN t::double precision END
$$;
```

`jsonb_to_recordset` with typed columns aborts the whole query on one bad value; ingestion is not yet clean.

### 2.3 `mv_sku` — one row per SKU

```sql
CREATE MATERIALIZED VIEW in_use.mv_sku AS
SELECT DISTINCT ON (product_id)
  product_id,
  product->>'sku_code'            AS sku_code,
  product->>'family'              AS family,
  taxonomy->>'category'           AS category,
  product->>'url'                 AS url,
  taxonomy->'decoded'             AS decoded,
  details->'completeness'         AS completeness,
  details->'sources'              AS sources,
  (details->'completeness'->>'has_price')::boolean AS has_price,
  jsonb_array_length(COALESCE(details->'facts','[]'::jsonb)) AS fact_count
FROM in_use.product_chunks
WHERE is_active AND product_id IS NOT NULL
ORDER BY product_id, id;

CREATE UNIQUE INDEX ON in_use.mv_sku (product_id);
CREATE UNIQUE INDEX ON in_use.mv_sku (sku_code);
CREATE INDEX ON in_use.mv_sku (category, family);
```

### 2.4 `mv_fact` — one row per (SKU, fact)

```sql
CREATE MATERIALIZED VIEW in_use.mv_fact AS
SELECT
  s.sku_code, s.family, s.category,
  f->>'canonical_spec_id'              AS spec_id,
  f->>'spec_label'                     AS spec_label,
  NULLIF(f->>'unit','')                AS unit,
  in_use.safe_num(f->>'value')         AS value_num,
  in_use.safe_num(f->>'value_min')     AS value_min,
  in_use.safe_num(f->>'value_max')     AS value_max,
  f->>'value_display'                  AS value_display,
  f->>'value_kind'                     AS value_kind,
  f->>'source_of_truth'                AS source_of_truth,
  (f->>'derived')::boolean             AS derived,
  f->>'fact_sentence'                  AS fact_sentence
FROM in_use.mv_sku s
JOIN in_use.product_chunks pc ON pc.product_id = s.product_id
CROSS JOIN LATERAL jsonb_array_elements(pc.details->'facts') AS f
WHERE pc.id = (SELECT min(id) FROM in_use.product_chunks x
               WHERE x.product_id = s.product_id AND x.is_active);

CREATE INDEX ON in_use.mv_fact (spec_id, value_num);
CREATE INDEX ON in_use.mv_fact (sku_code);
CREATE INDEX ON in_use.mv_fact (category, spec_id);
```

**Range semantics.** `value_kind` ∈ `scalar | range | set | text`. Comparison operators must respect it:

| op | predicate |
|---|---|
| `gte x` | `COALESCE(value_max, value_num) >= x` |
| `lte x` | `COALESCE(value_min, value_num) <= x` |
| `eq x`  | `x BETWEEN COALESCE(value_min, value_num) AND COALESCE(value_max, value_num)` |
| `contains s` | `value_display ILIKE '%s%'` |

Using `value_num` alone silently excludes every range-valued fact.

### 2.5 `mv_spec_registry`

```sql
CREATE MATERIALIZED VIEW in_use.mv_spec_registry AS
SELECT category, spec_id,
       mode() WITHIN GROUP (ORDER BY spec_label) AS spec_label,
       mode() WITHIN GROUP (ORDER BY unit)       AS unit,
       mode() WITHIN GROUP (ORDER BY value_kind) AS value_kind,
       count(DISTINCT sku_code)                  AS sku_count,
       min(COALESCE(value_min, value_num))       AS observed_min,
       max(COALESCE(value_max, value_num))       AS observed_max
FROM in_use.mv_fact
GROUP BY category, spec_id;
```

Spec vocabulary observed today: `rated_current_a`, `breaking_capacity_ka`, `rated_voltage_v`, `poles`, `modules`, `utilisation_category`, `price_inr`. `observed_min/max` lets the agent see that a threshold is unreachable before spending a call on it.

### 2.6 `mv_facet`

`taxonomy.path` is unpopulated; `taxonomy.decoded` gives a usable facet structure now.

```sql
CREATE MATERIALIZED VIEW in_use.mv_facet AS
SELECT category, family, d.key AS axis,
       COALESCE(d.value->>'meaning', d.value->>'code') AS meaning,
       d.value->>'code' AS code,
       count(*) AS sku_count
FROM in_use.mv_sku s
CROSS JOIN LATERAL jsonb_each(s.decoded) AS d
GROUP BY 1,2,3,4,5;
```

Axes present: `rating_idx`, `frame_class`, `frame`, `release`, `mounting`, `poles`, `breaking`, `acb_type`, `std_accessories`.

When `taxonomy.path` is populated, `taxonomy_browse` gains a `path` level above `category`; no other tool changes.

### 2.7 Refresh

Wholesale reload. `REFRESH MATERIALIZED VIEW` (non-concurrent) in dependency order — `mv_sku` → `mv_fact` → `mv_spec_registry`, `mv_facet` — as a `make refresh` target run post-load.

---

## 3. Tools

Built with `StructuredTool.from_function(func, args_schema=..., description=...)` so JSON schemas derive from Pydantic and cannot drift from the signature.

Descriptions below are the text to ship — they are the only thing steering tool choice, and each names the failure it prevents.

### 3.1 `taxonomy_browse`

```python
class TaxonomyBrowseArgs(BaseModel):
    category: str | None = None
    family: str | None = None
```

Returns by depth: categories with SKU counts → families in a category → decoded axes with values and counts.

```json
{"level":"facets","category":"ACB – WiNmaster 3","family":"ACB – WiNmaster 3",
 "sku_count":216,
 "axes":{"rating_idx":[{"code":"06","meaning":"630A","sku_count":24}],
         "poles":[{"code":"3P","meaning":3,"sku_count":120}]}}
```

> Browse the C&S catalogue structure: categories, the families inside them, and the ordering-code axes (rating, poles, breaking capacity, release type, mounting) that distinguish SKUs within a family, each with a SKU count. Use this first when you do not know what C&S sells in an area, and use it to tell "no such product exists" apart from "my filter was wrong" — an axis value with a non-zero count that returns no search hits means the filter is wrong.

### 3.2 `list_canonical_specs`

```python
class ListSpecsArgs(BaseModel):
    category: str | None = None
```

Returns `[{spec_id, spec_label, unit, value_kind, sku_count, observed_min, observed_max}]`.

> List the specification IDs available for a category, with units, value kinds, how many SKUs carry each, and the observed minimum and maximum in the catalogue. ALWAYS call this before using product_search filters in a category you have not queried yet. Spec IDs are exact strings — guessing them (e.g. 'breaking_capacity' instead of 'breaking_capacity_ka') returns nothing and you will wrongly conclude the product does not exist. Check observed_min/observed_max before filtering; a threshold outside that range cannot match.

### 3.3 `product_search`

```python
class SpecFilter(BaseModel):
    spec_id: str
    op: Literal["gte","lte","eq","contains"]
    value: float | str

class ProductSearchArgs(BaseModel):
    category: str | None = None
    family: str | None = None
    facets: dict[str, str] | None = None      # {"poles":"3P","rating_idx":"06"}
    filters: list[SpecFilter] = []
    text: str | None = None                    # sku_code trigram match
    return_specs: list[str] = []               # spec_ids to include per hit
    limit: int = 20
```

One `EXISTS` per filter against `mv_fact` using §2.4 range semantics; facets as `decoded->axis->>'code' = value`; `text` via the existing `gin_trgm_ops` index on `sku_code`.

Each hit returns `sku_code, family, category, decoded_summary, requested spec values, price_display, completeness.missing`.

> Find SKUs by specification filters, ordering-code facets, or code fragment. This is the PRIMARY tool for any question involving a number, rating, range, or superlative (cheapest, highest, smallest) — do not use document search for those. Filters use exact spec_id values from list_canonical_specs. Range-valued specs are matched against their min/max bounds, not a single number. Each result includes which specs are missing for that SKU, so you can tell "not published" from "not supported".

### 3.4 `get_sku`

```python
class GetSkuArgs(BaseModel):
    sku_code: str
    include: list[Literal["facts","decoded","content","sources"]] = ["facts","decoded"]
```

`facts` → all `mv_fact` rows including `fact_sentence`. `content` → the SKU's chunk texts (deduped as in §3.6). `sources` → `mv_sku.sources` plus `completeness`.

> Everything known about one SKU: its facts with units and value ranges, its decoded ordering code, and optionally its brochure text and source list. Use after product_search or taxonomy_browse has identified a sku_code. The returned completeness block lists specs absent from the source documents — treat those as "not published by C&S", not as zero or unsupported.

### 3.5 `compare_skus`

```python
class CompareSkusArgs(BaseModel):
    sku_codes: list[str]                 # 2..10
    spec_ids: list[str] | None = None    # default: union of specs present
```

Deterministic pivot: rows = spec_id, columns = SKU, cells = `value_display`, `null` where absent. No LLM, no free-form SQL.

> Side-by-side specification table for 2–10 named SKUs. Use this for any straightforward comparison instead of analytics_query — it is exact and cannot produce a malformed query. Empty cells mean the spec is not published for that SKU, not that the value is zero.

Exists because most comparison questions are a fixed pivot; routing them through free-form SQL adds a failure mode for nothing.

### 3.6 `search_documents`

```python
class SearchDocumentsArgs(BaseModel):
    query: str
    category: str | None = None
    family: str | None = None
    sku_code: str | None = None
    k: int = 6
```

pgvector cosine search over `product_chunks.embedding` with metadata pre-filter and **content deduplication**. Dedup is mandatory: the `technical` chunks for WiNmaster 2 and 3 are ordering-code decode tables identical across every SKU in the family, so an undeduplicated top-6 returns the same table six times.

```sql
WITH ranked AS (
  SELECT pc.id, pc.content, pc.chunk_type,
         pc.product->>'sku_code' AS sku_code,
         pc.embedding <=> :qvec AS dist,
         row_number() OVER (PARTITION BY md5(pc.content)
                            ORDER BY pc.embedding <=> :qvec) AS rn,
         count(*) OVER (PARTITION BY md5(pc.content)) AS shared_by_sku_count
  FROM in_use.product_chunks pc
  WHERE pc.is_active
    AND (:category IS NULL OR pc.taxonomy->>'category' = :category)
    AND (:family   IS NULL OR pc.product->>'family'   = :family)
    AND (:sku_code IS NULL OR pc.product->>'sku_code' = :sku_code)
)
SELECT * FROM ranked WHERE rn = 1 ORDER BY dist LIMIT :k;
```

Query vector comes from the externally-provided `embed()`.

> Semantic search over brochure text. Use ONLY for qualitative questions: how a feature works, what a salient-features list says, whether a product suits an application, what a standard requires. Never use it to find, rank, or compare numeric ratings — embeddings cannot distinguish 630 A from 800 A, or WX306 from WX308. Always pass a category or family filter. Results marked as shared across many SKUs are family-level marketing text, not specifications for one SKU.

### 3.7 `analytics_query`

Sub-agent, §5.

> Run a free-form analytical query across many SKUs — aggregates, rankings, distributions, or anything needing a pivot over more than ten products. Returns a result table with no interpretation. For a simple comparison of named SKUs use compare_skus instead. State the question in plain language and the shape of table you want back.

### 3.8 Not registered

`get_compatibility` and `get_assets` are deferred. Do not add them to the tool list until implemented — an unregistered tool cannot burn budget on failed calls.

---

## 4. Graph

### 4.1 State

```python
class Evidence(TypedDict):
    tool: str
    sku_code: str | None
    spec_id: str | None
    value_num: float | None
    value_min: float | None
    value_max: float | None
    value_display: str | None
    value_kind: str | None
    unit: str | None
    source_of_truth: str | None
    text: str | None

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: dict | None
    evidence: Annotated[list[Evidence], operator.add]
    clarify_count: int          # HARD CAP 2
    tool_calls_made: int        # HARD CAP 12
    assumptions: list[str]
    draft: str | None
    validation: dict | None        # reserved; validator is dormant
```

`evidence` is append-only and is the only source the composer may use for
catalogue claims.

### 4.2 Topology

```
START → planner
          ├ needs_clarification and clarify_count < 2 → clarify → planner
          └ otherwise                                          → agent
agent → tools (ToolNode) → record_evidence → agent   [until no tool_calls or budget hit]
      → composer → END
```

Checkpointer: `PostgresSaver` (`MemorySaver` in tests) — required for `interrupt()`.

**planner** — `structured()` → `Plan{intent, categories[], target_specs[], known_params, open_params[], needs_clarification, strategy}`. Merges clarify answers on re-entry.

**clarify** — `interrupt()`, up to 3 questions. `clarify_count` incremented here; **the cap is enforced in the conditional edge, not the prompt**, so no model can talk past it. On cap, remaining `open_params` become `assumptions` and the run continues.

**agent** — `get_model("agent").bind_tools(TOOLS).invoke(messages)`. Conditional edge: `tool_calls` present and budget remaining → `tools`; otherwise → `composer`.

**tools** — stock `ToolNode(TOOLS)`. Handles parallel calls, error wrapping, `ToolMessage` construction.

**record_evidence** — reads `ToolMessage`s added since last visit, parses each into `Evidence` with a per-tool parser (plain Python, no LLM), increments `tool_calls_made`. Separate node so `ToolNode` stays stock.

| Tool | Evidence produced |
|---|---|
| `product_search`, `get_sku`, `compare_skus` | one per fact, all numeric and provenance fields |
| `search_documents` | one per chunk, text only |
| `analytics_query` | one per numeric cell |
| `taxonomy_browse`, `list_canonical_specs` | counts only — not citable as specs |

---

## 5. Analytics sub-agent

Compiled subgraph exposed as one tool. Own context. Returns a table only.

```
START → plan_sql → write_sql → execute_sql → shape_result → END
                       ^            |
                       └──(error, retries < 2)──┘
```

`execute_sql` runs the query as given. **No guardrails in v1** — mark the call site `# GUARDRAIL_HOOK` for later addition of read-only role, `statement_timeout`, single-statement enforcement, LIMIT wrapper, row cap.

```python
class SqlResult(BaseModel):
    columns: list[str]
    rows: list[list]
    sql: str
    row_count: int
    note: str          # what it did and excluded — no inference
    error: str | None
```

Log every emitted SQL string regardless of outcome; mine later to decide which views to add.

---

## 6. Prompts

One file per node in `prompts/`.

### 6.1 `prompts/planner.md`

```
You plan how to answer questions about C&S Electric's product catalogue.

The catalogue is organised as: category (e.g. "ACB – WiNmaster 3") → family → SKU.
Every SKU has an ordering code (e.g. WX306L3P1MDOA(S)) which is also its identifier.
Ordering codes decode into axes: current rating, poles, breaking capacity, frame,
release/trip unit, mounting, and standard accessories.

Classify the question into exactly one intent:
- lookup   : facts about one identified SKU or family
- compare  : several SKUs against shared specifications
- select   : "which product should I use for X" — needs a recommendation
- explain  : how something works, what a code means, or general electrical guidance

Then produce a plan:

1. Name the categories in scope. If unsure, leave empty — the agent will browse.
2. List the specifications likely needed, in plain words. Exact spec IDs are looked
   up later by the agent.
3. Put every parameter the user gave into known_params.
4. Put missing parameters into open_params.
5. Set needs_clarification TRUE only if a missing parameter would change WHICH SKU or
   FAMILY is recommended. Load current, system voltage, pole count, breaking capacity
   requirement, and fixed-vs-drawout mounting qualify. Standard-accessory suffix and
   terminal type do NOT — those are minor variants, and the answer can cover both.
6. Never ask for something the user already stated.

Reply with ONLY the JSON object.
```

### 6.2 `prompts/clarify.md`

```
Ask at most 3 questions to fill the open parameters. Each question must:
- be answerable in one short line by an electrical contractor or panel builder
- include a suggested default in parentheses so the user can skip it
- use the terms the C&S catalogue uses (rated current in A, poles, breaking capacity
  in kA, fixed or drawout) rather than invented jargon

Do not explain why you are asking. Do not preface with pleasantries.
Output the questions as a numbered list and nothing else.
```

### 6.3 `prompts/agent.md` (system message)

```
You answer questions about C&S Electric products using the provided tools.

CATALOGUE SHAPE
Products are identified by their ordering code (sku_code), e.g. WX306L3P1MDOA(S) or
AH06BCSMP3.1MF(S). Codes decode into axes — rating, poles, breaking capacity, frame,
release, mounting — and taxonomy_browse exposes those axes with counts. Specifications
are stored under exact spec IDs such as rated_current_a, breaking_capacity_ka,
rated_voltage_v, poles, modules, utilisation_category, price_inr.

TOOL DISCIPLINE
- Numbers, ratings, ranges, superlatives (cheapest, highest, smallest) → product_search,
  after list_canonical_specs for that category.
- Comparing 2-10 named SKUs → compare_skus. Do not use analytics_query for this.
- Aggregates, distributions, or rankings over many SKUs → analytics_query.
- How something works, what a feature does, application suitability → search_documents.
- Everything about one SKU → get_sku.
- Never state a specification you did not retrieve from a tool.

SEQUENCING
taxonomy_browse to find the category and its axes → list_canonical_specs to learn the
exact spec IDs and their observed ranges → product_search to shortlist → get_sku or
compare_skus for detail. Skip steps you already have results for. Call tools in
parallel when they are independent.

READING THE DATA CORRECTLY
1. Specs have a value_kind: scalar, range, set, or text. A range spec has value_min and
   value_max — quote the range, not a single number.
2. Check observed_min and observed_max from list_canonical_specs before filtering. A
   threshold outside that range cannot match anything, and an empty result there means
   the catalogue does not go that far, not that your query failed.
3. Every spec carries source_of_truth:
   - "pricelist_table" — published by C&S in the pricelist.
   - "code_grammar" — DERIVED by decoding the ordering code, not read from a table.
     Still reliable, but say so when reporting it.
4. Each SKU carries completeness.missing, listing specs absent from the source
   documents. If a spec you need is in that list, report it as not published by C&S.
   Never treat a missing spec as zero, and never assume the product lacks the feature.
5. Price may be "POR" (price on request) with no numeric value. Report it as POR and
   point to the nearest C&S branch office. A SKU with POR pricing cannot be ranked by
   price — say so rather than excluding it silently.
6. search_documents results marked as shared across many SKUs are family-level or
   category-level marketing text. Do not attribute them as specifications of one SKU.
7. Where a rating depends on a condition — voltage, pole count, ambient temperature —
   report the condition alongside the value. If the stored fact does not state its
   condition, say the condition is not specified rather than assuming one.

If a tool returns an error, read it and fix the arguments. Do not switch to document
search to work around a failed structured query.

If the catalogue does not cover something, say so plainly. Do not substitute a
different product silently.

Stop calling tools once you have what the plan asked for.

Plan for this question:
{plan_json}
```

### 6.4 `prompts/composer.md`

```
Write the answer using ONLY the evidence below.

Evidence (every retrieved fact, with its source):
{evidence_table}

Assumptions made because the user did not specify:
{assumptions}

RULES
1. Every specification you state must appear in the evidence table. If it is not there,
   either omit it or mark it clearly as general engineering practice rather than a C&S
   specification.
2. Cite as: SKU code, then how the value is known —
   - source_of_truth "pricelist_table" → "(C&S pricelist)"
   - source_of_truth "code_grammar"    → "(derived from ordering code)"
   Page-level citation is not available yet; do not invent page numbers.
3. Range-valued specs are reported as ranges, e.g. "630-800 A", not a single figure.
4. Conditional ratings are reported with their condition ("Icu 80 kA at 415 V"). If the
   evidence does not carry the condition, write "voltage not specified in source"
   rather than assuming a value.
5. A spec listed in completeness.missing is reported as "not published by C&S" — never
   as zero, absent, or unsupported.
6. Price on request is reported as POR with a pointer to the nearest C&S branch office,
   not as a missing or zero price. If the user asked for the cheapest option and some
   candidates are POR, name them and state that they could not be ranked.
7. Separate catalogue facts from general engineering knowledge. Use two clearly
   labelled sections when the answer contains both.
8. Open by listing the assumptions you worked from, if any.
9. If you recommend more than one component together (breaker plus release, contactor
   plus accessory), add: "Component compatibility has not been verified against the
   accessory matrix — confirm with C&S before ordering."
10. If the catalogue does not cover part of the question, say which part.
11. Neutral, professional tone. No sales language.
```

### 6.5 `prompts/analytics_write_sql.md`

```
Write ONE PostgreSQL SELECT statement answering the question below.

Views available (read-only):

  in_use.mv_sku(sku_code, family, category, url, decoded jsonb,
                completeness jsonb, has_price bool, fact_count int)

  in_use.mv_fact(sku_code, family, category, spec_id, spec_label, unit,
                 value_num, value_min, value_max, value_display, value_kind,
                 source_of_truth, derived, fact_sentence)

  in_use.mv_spec_registry(category, spec_id, spec_label, unit, value_kind,
                          sku_count, observed_min, observed_max)

  in_use.mv_facet(category, family, axis, code, meaning, sku_count)

mv_fact is long-format: one row per (sku_code, spec_id). To compare specs across SKUs,
pivot with FILTER or crosstab.

Spec IDs in scope:
{spec_registry}

RULES
- One statement. SELECT only.
- value_kind may be scalar, range, set, or text. Use these predicates:
    gte x  ->  COALESCE(value_max, value_num) >= x
    lte x  ->  COALESCE(value_min, value_num) <= x
    eq  x  ->  x BETWEEN COALESCE(value_min, value_num)
                     AND COALESCE(value_max, value_num)
  Comparing value_num alone silently drops every range-valued fact.
- value_num is NULL for text and set specs; use value_display for those.
- price_inr may have value_num NULL with value_display 'POR'. Exclude POR rows from
  numeric price ranking with an explicit filter, and count them separately so they can
  be reported.
- A missing spec row is not a zero. Use LEFT JOIN and report NULL rather than
  substituting 0.
- Identify products by sku_code. Never return product_id.
- Return the columns requested in output_shape, using those names.

Output only the SQL. No explanation, no fences.
```

### 6.6 `prompts/analytics_shape.md`

```
Turn this result set into the requested output shape.

Write a one-line note stating what was excluded and why — rows dropped for missing
specs, SKUs excluded from price ranking because they are POR, or ranges collapsed.

Do NOT interpret, rank by judgement, or recommend anything.
```

---

## 7. Numeric fidelity validator (dormant)

Deterministic, no LLM. `validation/numeric_fidelity.py`.

1. Strip ordering codes and standard references from the draft **first** (`WX306L3P1MDOA(S)`, `AH06BCSMP3.1MF(S)`, `CS250`, `IEC 60947-2`). Skipping this makes the `06` in `WX306` fail on every answer.
2. Extract remaining `(number, unit, span)` triples.
3. Exclude numbers present verbatim in the user's message, list ordinals, and years.
4. A figure passes if it matches `value_num`, **or** falls within `[value_min, value_max]` for a range-valued spec, **or** matches `value_display` for a `text`/`set` spec. Without the middle clause, correctly-reported ranges fail.
5. Assert that any matched fact carrying a stated condition has that condition in the same sentence.
6. Unmatched → `fail` with the offending spans.

Dormant routing behavior if re-enabled: first failure → composer with the spans
listed. Second → strip those sentences and append *"Some figures could not be
verified against the catalogue and were removed."*

Report `numbers_total / matched / unmatched[]` to the trace. Headline metric when comparing Sonnet against the Qwen profiles.

The implementation is retained for future evaluation, but it is not registered
in the active graph. The composer performs its own evidence check and routes
directly to `END`.

---

## 8. Repository layout

```
cs_agent/
  config/endpoints.yaml
  llm/factory.py  llm/structured.py
  db/views.sql  db/refresh.py
  tools/schemas.py  tools/descriptions.py  tools/impl.py  tools/registry.py
  graph/state.py  graph/build.py
  graph/nodes/{planner,clarify,agent,record_evidence,composer,validator}.py
  subgraphs/analytics/{build,nodes,tool}.py
  validation/numeric_fidelity.py
  prompts/*.md
  run.py
```

---

## 9. Build order

| # | Step | Done when |
|---|---|---|
| 1 | `llm/factory.py` + `endpoints.yaml` | Same `get_model()` reaches Anthropic and a local vLLM; `bind_tools` round-trips on both |
| 2 | `db/views.sql` + refresh | Four views populated from live data |
| 3 | Tools 3.1–3.6 against the views | Each invokable from a REPL, returning correct rows for the three ACB categories |
| 4 | State + evidence parsers | `ToolMessage` output becomes Evidence with no LLM involved |
| 5 | `agent` + `ToolNode` + `record_evidence` + `composer` | End-to-end answer on 5 real questions |
| 6 | Numeric fidelity validator | An injected wrong figure is caught and removed |
| 7 | `planner` + `clarify` (cap 2) | Vague question triggers one clarify round, then proceeds |
| 8 | Analytics subgraph | Cross-SKU aggregate returns a correct table |
| 9 | Eval harness | Metrics per endpoint profile |
| 10 | Model swap | `endpoints.yaml` edit only |

Steps 1–7 are demoable on the three ACB categories already loaded.

---

## 10. Known data issues the tools surface but cannot fix

Listed so the implementer does not mistake them for bugs in the agent:

- `chunk_type` is not yet consistent — the AH-AHA `identity` chunk is an ordering-code breakdown, the WiNmaster 2 `identity` chunk is price and rating sentences. **`chunk_type` is deliberately absent from every tool's filter surface** until it means one thing.
- Facts carry no `conditions` field, so a rating like "Icu 80 kA" has no voltage attached. Prompts instruct the agent to say the condition is unspecified rather than assume one. This becomes acute when MCCBs land — one breaker spans five kA values across five voltages under the same spec_id.
- Provenance is source-file level, not page level. Composer citation rule is relaxed accordingly.
- Some rows look mis-typed: `CS-WM2-AKI-1-AB` is an ACB with `rated_current_a` = 0.2 A and a ₹10,960 MRP, with content ending `"0.2 ......... 1, OFF."`. `frame_class B` decodes to `"unknown"`. `completeness.missing` lists `price_inr` on a SKU that has a `price_inr` fact of POR.
- Family-level text (ordering-code decode tables) is stored and embedded once per SKU. `search_documents` dedups at query time; the durable fix is a `scope: sku|family|category` field on the chunk.