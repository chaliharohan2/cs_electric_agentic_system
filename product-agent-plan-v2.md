# C&S Product Agent — Implementation Plan v2 (Multi-Agent)

Supersedes `product-agent-plan.md` and `updated_implementation_plan.md`. Target DB: `cs_electric_v2`.

**Change of shape:** one tool-using agent becomes a planner that fans out to five specialist sub-agents in parallel, each with its own private context and structured report, reconciled by a composer that may send targeted follow-up briefs.

**Retained unchanged:** model layer (§1 of v1), analytics sub-agent internals, `run.py` CLI shape, observability.

**Dormant:** `validator` node stays in the tree, unwired.

---

## 0. What the v2 data changes

Verified against the samples and the pipeline reference. Five things drive design decisions below.

**`sku_code` is not always the canonical code, and codes outnumber products.** 9,703 codes map to 9,115 `product_id`s. `CG24025W` has `canonical_code: "CG24025WNR"` and `also_published_as: ["CG24025WNR"]`, with `alias_reason: "pricelist prints this code with an NR suffix"`. Any lookup must search all three fields, so code resolution gets its own view and its own tool.

**`taxonomy.category` is gone.** Replaced by `path` (2–4 levels) plus `levels[]` carrying URL, description, `is_leaf`, `page_type`, and the full category-page markdown. `_no_category` is a holding folder whose sub-levels are pricelist section names, not published categories — those rows must be flagged, not presented as taxonomy.

**`chunk_type` is now trustworthy** — 19 values, one row per `(product_id, chunk_type)` by construction, zero duplicates measured. In v1 I kept it out of the tool surface because it was inconsistent; that decision is reversed. It is now the primary filter for the compliance agent (`standards`) and a strong one for spec selection (`ratings`, `technical_data`).

**Price is the most dangerous field in the database.** Seven `price_status` values, and three open extraction defects: multi-column price binding (~1,190 code slots over 40 pages, a code can receive a sibling's price), AH/AHA two-level headers (82 cells wrongly reading as POR), and merged price cells (~53 records). Plus `price_observations[].context` may name a different code than the SKU. Pricing therefore gets a dedicated tool that surfaces status and context-mismatch flags rather than being a plain fact.

**`composite` is a fifth `value_kind`, affecting 3,210 products.** Printed text preserved, no queryable number, `value_min`/`value_max` null. Numeric filters silently miss all of them unless the tool counts and reports the exclusion.

---

## 1. Configuration

All caps are config, not constants. `cs_agent/config/limits.yaml`:

```yaml
global_tool_budget: 100        # across all sub-agents in one turn
per_agent_tool_budget: 20      # ceiling inside one sub-agent
composer_revision_rounds: 2
clarify_rounds: 2
tool_failure_limit: 3          # per sub-agent
max_parallel_agents: 5
analytics_max_queries: 4
```

Env overrides: `CS_GLOBAL_TOOL_BUDGET`, `CS_COMPOSER_REVISIONS`, etc.

---

## 2. Derived views

`product` and `details` remain byte-identical across all chunks of a SKU (verified), so `DISTINCT ON (product_id)` is still valid. Eight views now.

### 2.1 `mv_sku`

```sql
CREATE MATERIALIZED VIEW in_use.mv_sku AS
SELECT DISTINCT ON (product_id)
  product_id,
  product->>'sku_code'                            AS sku_code,
  COALESCE(product->>'canonical_code',
           product->>'sku_code')                  AS canonical_code,
  product->>'family'                              AS family,
  product->>'description'                         AS description,
  product->>'url'                                 AS url,
  product->>'price_status'                        AS price_status,
  product->>'peer_group'                          AS peer_group,
  product->'decoded'                              AS decoded,
  product->'attributes'                           AS attributes,
  product->'comparable_on'                        AS comparable_on,
  product->'related_codes'                        AS related_codes,
  product->'market_segments'                      AS market_segments,
  product->'also_published_as'                    AS also_published_as,
  product->>'alias_reason'                        AS alias_reason,
  taxonomy->'path'                                AS path,
  (taxonomy->>'depth')::int                       AS depth,
  array_to_string(ARRAY(SELECT jsonb_array_elements_text(taxonomy->'path')),
                  ' > ')                          AS path_text,
  taxonomy->'path'->>0                            AS path_l1,
  taxonomy->'path'->>1                            AS path_l2,
  taxonomy->'path'->>2                            AS path_l3,
  (taxonomy->'path'->>0 = '_no_category')         AS is_no_category,
  taxonomy->'headings'                            AS headings,
  details->'spec_ids'                             AS spec_ids,
  details->'derived'                              AS derived,
  details->'sources'                              AS sources,
  details->'extraction'                           AS extraction,
  details->'extraction'->'missing'                AS extraction_missing,
  details->'extraction'->>'confidence'            AS extraction_confidence,
  jsonb_array_length(COALESCE(details->'facts','[]'::jsonb)) AS fact_count
FROM in_use.product_chunks
WHERE is_active AND product_id IS NOT NULL
ORDER BY product_id, id;

CREATE UNIQUE INDEX ON in_use.mv_sku (product_id);
CREATE INDEX ON in_use.mv_sku (sku_code);
CREATE INDEX ON in_use.mv_sku (family);
CREATE INDEX ON in_use.mv_sku (path_l1, path_l2, path_l3);
CREATE INDEX ON in_use.mv_sku USING gin (family gin_trgm_ops);
CREATE INDEX ON in_use.mv_sku USING gin (path_text gin_trgm_ops);
CREATE INDEX ON in_use.mv_sku USING gin (market_segments jsonb_path_ops);
```

### 2.2 `mv_code_alias` — the resolution surface

```sql
CREATE MATERIALIZED VIEW in_use.mv_code_alias AS
SELECT product_id, sku_code AS code, 'sku' AS role FROM in_use.mv_sku
UNION
SELECT product_id, canonical_code, 'canonical' FROM in_use.mv_sku
  WHERE canonical_code IS DISTINCT FROM sku_code
UNION
SELECT s.product_id, a.code, 'alias'
FROM in_use.mv_sku s
CROSS JOIN LATERAL jsonb_array_elements_text(COALESCE(s.also_published_as,'[]'::jsonb)) AS a(code);

CREATE INDEX ON in_use.mv_code_alias (code);
CREATE INDEX ON in_use.mv_code_alias USING gin (code gin_trgm_ops);
CREATE INDEX ON in_use.mv_code_alias (product_id);
```

### 2.3 `mv_fact`

`fact.source` is polymorphic — `null`, `"brochure"`, `{"pdf":…,"page":…}`, or a section-heading string. Branch on `jsonb_typeof`.

```sql
CREATE MATERIALIZED VIEW in_use.mv_fact AS
SELECT
  s.product_id, s.sku_code, s.family, s.path_text,
  f->>'canonical_spec_id'          AS spec_id,
  f->>'spec_label'                 AS spec_label,
  NULLIF(f->>'unit','')            AS unit,
  (f->>'canonical')::boolean       AS is_canonical_spec,
  in_use.safe_num(f->>'value')     AS value_num,
  in_use.safe_num(f->>'value_min') AS value_min,
  in_use.safe_num(f->>'value_max') AS value_max,
  f->>'value_display'              AS value_display,
  f->>'value_kind'                 AS value_kind,
  f->>'source_of_truth'            AS source_of_truth,
  CASE WHEN jsonb_typeof(f->'source')='object'
       THEN f->'source'->>'pdf' END                     AS source_pdf,
  CASE WHEN jsonb_typeof(f->'source')='object'
       THEN (f->'source'->>'page')::int END             AS source_page,
  CASE WHEN jsonb_typeof(f->'source')='string'
        AND f->>'source' <> 'brochure'
       THEN f->>'source' END                            AS source_heading,
  f->>'fact_sentence'              AS fact_sentence
FROM in_use.mv_sku s
JOIN in_use.product_chunks pc ON pc.product_id = s.product_id
CROSS JOIN LATERAL jsonb_array_elements(pc.details->'facts') AS f
WHERE pc.id = (SELECT min(id) FROM in_use.product_chunks x
               WHERE x.product_id = s.product_id AND x.is_active);

CREATE INDEX ON in_use.mv_fact (spec_id, value_num);
CREATE INDEX ON in_use.mv_fact (product_id);
CREATE INDEX ON in_use.mv_fact (family, spec_id);
CREATE INDEX ON in_use.mv_fact (value_kind);
```

**Range predicates** (unchanged, now with an explicit composite rule):

| op | predicate |
|---|---|
| `gte x` | `COALESCE(value_max, value_num) >= x` |
| `lte x` | `COALESCE(value_min, value_num) <= x` |
| `eq x` | `x BETWEEN COALESCE(value_min, value_num) AND COALESCE(value_max, value_num)` |
| `contains s` | `value_display ILIKE '%s%'` |

`composite` rows have all three numerics null and **cannot satisfy any numeric predicate**. Every tool applying a numeric filter must count them separately and return `composite_excluded: n` (§3.4).

### 2.4 `mv_price`

```sql
CREATE MATERIALIZED VIEW in_use.mv_price AS
SELECT
  s.product_id, s.sku_code, s.canonical_code, s.price_status,
  (o->>'price')::numeric        AS price,
  o->>'price_list'              AS price_list,
  o->>'source_pdf'              AS source_pdf,
  (o->>'source_page')::int      AS source_page,
  o->>'effective_date'          AS effective_date,
  o->>'price_status'            AS observation_status,
  o->>'context'                 AS context,
  (o->>'context' ILIKE '%'||s.sku_code||'%'
   OR o->>'context' ILIKE '%'||s.canonical_code||'%') AS context_names_own_code
FROM in_use.mv_sku s
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(s.price_observations,'[]'::jsonb)) AS o;
```

`context_names_own_code = false` is the deterministic detector for the mismatch you flagged (`CSDB7SEGDD04` carrying context `CSDBPHSCDD12`). The tool surfaces it; the composer discloses it. No judgement call needed at runtime.

### 2.5 `mv_source` — citation surface

Parses `details.sources[]` into typed references. Brochures cite the `.md` with no page, per your answer.

```sql
CREATE MATERIALIZED VIEW in_use.mv_source AS
SELECT product_id,
  CASE WHEN src LIKE 'Brochure:%'     THEN 'brochure_md'
       WHEN src LIKE 'Product page:%' THEN 'product_page'
       WHEN src ~ '\.pdf p[0-9]+$'    THEN 'pricelist_pdf'
       ELSE 'other' END AS ref_type,
  CASE WHEN src LIKE 'Brochure:%'
       THEN regexp_replace(src, '^Brochure:\s*([^ ]+).*$', '\1')
       WHEN src ~ '\.pdf p[0-9]+$'
       THEN regexp_replace(src, '^(.*\.pdf) p[0-9]+$', '\1')
       WHEN src LIKE 'Product page:%'
       THEN regexp_replace(src, '^Product page:\s*', '')
       ELSE src END AS ref_name,
  CASE WHEN src ~ '\.pdf p[0-9]+$'
       THEN (regexp_replace(src, '^.*\.pdf p([0-9]+)$', '\1'))::int END AS page
FROM in_use.mv_sku s
CROSS JOIN LATERAL jsonb_array_elements_text(COALESCE(s.sources,'[]'::jsonb)) AS t(src);
```

### 2.6 `mv_spec_registry`

```sql
CREATE MATERIALIZED VIEW in_use.mv_spec_registry AS
SELECT family, spec_id,
       mode() WITHIN GROUP (ORDER BY spec_label)  AS spec_label,
       mode() WITHIN GROUP (ORDER BY unit)        AS unit,
       mode() WITHIN GROUP (ORDER BY value_kind)  AS value_kind,
       bool_or(is_canonical_spec)                 AS is_canonical_spec,
       count(DISTINCT product_id)                 AS sku_count,
       count(*) FILTER (WHERE value_kind='composite') AS composite_count,
       min(COALESCE(value_min, value_num))        AS observed_min,
       max(COALESCE(value_max, value_num))        AS observed_max
FROM in_use.mv_fact
GROUP BY family, spec_id;
```

`is_canonical_spec` separates the 64-term controlled vocabulary from the retained long tail — the compliance agent uses this to discover standards-related specs at runtime rather than from a hardcoded list.

### 2.7 `mv_facet` and `mv_chunk_index`

`mv_facet` as before, keyed on `family` instead of the departed `category`.

```sql
CREATE MATERIALIZED VIEW in_use.mv_chunk_index AS
SELECT product_id, product->>'sku_code' AS sku_code,
       chunk_type, id AS chunk_id,
       taxonomy->'headings' AS headings,
       length(content) AS content_len
FROM in_use.product_chunks WHERE is_active;

CREATE INDEX ON in_use.mv_chunk_index (product_id, chunk_type);
CREATE INDEX ON in_use.mv_chunk_index (chunk_type);
```

Lets a tool answer "does this SKU have a `standards` chunk" without touching the 79k-row table.

### 2.8 Full-text column

Embeddings will be loaded before use, but a lexical index costs nothing and makes `search_documents` degrade gracefully if a query embeds poorly:

```sql
ALTER TABLE in_use.product_chunks
  ADD COLUMN content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX ON in_use.product_chunks USING gin (content_tsv);
```

Refresh order: `mv_sku` → `mv_code_alias`, `mv_fact`, `mv_price`, `mv_source` → `mv_spec_registry`, `mv_facet`, `mv_chunk_index`.

---

## 3. Tools

Two registries: `SHARED_TOOLS` and per-agent additions. Each sub-agent binds `SHARED_TOOLS + AGENT_TOOLS[name]`.

### 3.1 `resolve_product` — new, shared

```python
class ResolveProductArgs(BaseModel):
    query: str                       # code fragment, misspelling, or description
    family_hint: str | None = None
    limit: int = 8
```

Three-stage cascade, stopping at the first stage that returns hits:

1. exact match on `mv_code_alias.code` (case/space/hyphen-normalised)
2. trigram similarity over `mv_code_alias.code` with `similarity() >= 0.35`, ordered descending
3. trigram over `mv_sku.description` + `family`, plus full-text over `content`

Returns `[{sku_code, canonical_code, family, path_text, match_role, score, description}]` plus `resolution: exact|fuzzy|descriptive` and `alias_note` when the input matched a non-canonical spelling.

> **Description:** Resolve a product code, partial code, misspelling, or plain-language product description into real SKU codes. ALWAYS call this before get_sku, compare_skus, or get_price_detail when the user typed a code rather than you retrieving it from a search result. C&S prints the same product under different spellings (CG24025W vs CG24025WNR, CTF 160 vs CTF-160), so an exact-match failure does not mean the product does not exist. Returns ranked candidates with a match score and tells you whether the code you supplied is the canonical one.

### 3.2 `taxonomy_browse` — rewritten for paths

```python
class TaxonomyBrowseArgs(BaseModel):
    path: list[str] | None = None    # drill down, e.g. ["Low Voltage Products and Solutions","Circuit Breakers"]
    market_segment: str | None = None
    include_facets: bool = False     # only meaningful at leaf/family level
```

Returns children of the given path with SKU counts, each child's published description and URL from `levels[]`, `is_leaf`, and — at leaf level — decoded facet axes. Rows under `_no_category` are returned in a separate `uncategorised` block with a note that these are pricelist section names, not published categories.

> **Description:** Walk the C&S catalogue hierarchy level by level (2–4 levels deep, e.g. Low Voltage Products and Solutions > Circuit Breakers > Air Circuit Breakers > ACB – AH-AHA), returning each child with its published description, page URL, and SKU count. At the family level it also returns the ordering-code facet axes. Use this to find what C&S sells in an area. **Browsing alone never answers a product question** — once you have a family, you must call product_search or resolve_product to get actual SKUs. A non-zero SKU count with no search hits means your filter is wrong, not that the family is empty.

### 3.3 `list_canonical_specs` — shared

```python
class ListSpecsArgs(BaseModel):
    family: str | None = None
    spec_id_contains: str | None = None   # runtime discovery, e.g. "standard", "test"
    canonical_only: bool = False
```

Returns `[{spec_id, spec_label, unit, value_kind, is_canonical_spec, sku_count, composite_count, observed_min, observed_max}]`.

`spec_id_contains` is how the compliance agent discovers its own vocabulary at runtime — `list_canonical_specs(family=…, spec_id_contains="standard")` surfaces `applicable_standard`, `reference_standards`; `"test"` surfaces `glow_wire_test`, `damp_heat_test`, `vibration_test`.

> **Description:** List the specification IDs that exist for a family, with units, value kinds, SKU counts, and observed min/max. Call this before using product_search filters on a family you have not queried this turn — spec IDs are exact strings and guessing them returns nothing. Use spec_id_contains to discover specs by topic (e.g. "standard", "test", "trip", "voltage") rather than assuming names. is_canonical_spec marks the 64-term controlled vocabulary; other specs are real but appear in fewer products. composite_count warns how many values for that spec are unparsed text that numeric filters will skip.

### 3.4 `product_search` — shared, primary

```python
class SpecFilter(BaseModel):
    spec_id: str
    op: Literal["gte","lte","eq","contains"]
    value: float | str

class ProductSearchArgs(BaseModel):
    path: list[str] | None = None
    family: str | None = None
    facets: dict[str, str] | None = None
    filters: list[SpecFilter] = []
    market_segment: str | None = None
    price_status: list[str] | None = None
    has_chunk_type: list[str] | None = None     # e.g. ["standards"]
    text: str | None = None
    return_specs: list[str] = []
    limit: int = 20
```

Response envelope:

```json
{"hits": [...], "total_matched": 47, "composite_excluded": 12,
 "filters_applied": [...], "widening_hint": null}
```

`composite_excluded` is mandatory whenever a numeric filter runs — 3,210 products carry unparsed composite values that no numeric predicate can match, and silently dropping them is the difference between "C&S has nothing" and "C&S has products whose value we could not parse". When zero hits, `widening_hint` names the filter that eliminated the most candidates.

> **Description:** Find SKUs by specification filters, ordering-code facets, catalogue path, market segment, price status, or presence of a chunk type. This is the PRIMARY tool for any question involving a number, rating, range, or superlative — do not use document search for those. Filters use exact spec_id values from list_canonical_specs. Range-valued specs match on their min/max bounds. The response reports composite_excluded: products whose value for a filtered spec is printed text that could not be parsed into a number — they are NOT ruled out, they are unknown, and you must say so if the count is non-zero. On zero hits, read widening_hint before concluding the product does not exist.

### 3.5 `get_sku` — shared

```python
class GetSkuArgs(BaseModel):
    sku_code: str
    include: list[Literal["facts","decoded","chunks","sources","price","peers"]] = ["facts","decoded","sources"]
    chunk_types: list[str] | None = None    # when include contains "chunks"
```

Always returns `extraction.missing` and `extraction.confidence` alongside whatever was requested.

> **Description:** Everything known about one SKU: typed facts with units and ranges, decoded ordering code, source references, optionally its brochure chunk text (filter with chunk_types), price detail, and peer group. Resolve the code with resolve_product first if the user typed it. The returned extraction.missing lists specs the pipeline expected but could not find in any source — report those as "not published by C&S", never as zero or unsupported. extraction.confidence tells you how much of the source was readable.

### 3.6 `get_price_detail` — new, shared

```python
class GetPriceDetailArgs(BaseModel):
    sku_codes: list[str]     # 1..10
```

Returns per SKU: `price_status`, every observation with `price`, `price_list`, `source_pdf`, `source_page`, `effective_date`, `context`, and `context_names_own_code`. Adds `quotable: bool` — false when `price_status` is `multiple_variants` or when every observation has `context_names_own_code = false`.

> **Description:** Retrieve pricing for up to 10 SKUs with full provenance. Price is not a plain fact in this catalogue and must be read carefully. price_status is load-bearing: `listed` is a published 2026 MRP; `por` means price on request; `multiple_variants` means the pricelist row covers several variants at different prices and **no single figure is correct — never quote a number for these**; `brochure_price_only` may predate the current revision; `not_listed`/`not_in_pricelist`/`not_offered` each mean something different. Each observation carries the pricelist row context it was read from; when context_names_own_code is false the figure was read from a row naming a different code and must be reported with that caveat. Prices are MRP, inclusive of GST, and are not what a distributor pays.

### 3.7 `compare_skus` — comparison agent

```python
class CompareSkusArgs(BaseModel):
    sku_codes: list[str]              # 2..10
    spec_ids: list[str] | None = None # default: intersection of comparable_on, else union present
```

Defaults its axes to `product.comparable_on` when the SKUs share a `peer_group` — this is the field the pipeline already computed for exactly this purpose. Returns the pivot plus `peer_group_match: bool` and `axes_source: comparable_on | union`.

> **Description:** Side-by-side specification table for 2–10 SKUs. Defaults its comparison axes to the catalogue's own comparable_on list when the products share a peer group, which is more reliable than picking specs yourself. Empty cells mean not published for that SKU, not zero. peer_group_match: false warns that the products are not from a comparable set, so differences may be structural rather than meaningful.

### 3.8 `get_peer_group` — comparison + discovery

Returns the peer set for a SKU with `comparable_on`, `related_codes`, and each peer's differentiating decoded axes.

> **Description:** Given one SKU, return the products C&S groups it with, the specs the catalogue considers comparable across that group, and what distinguishes each peer. Use this to build a shortlist for comparison, or to answer "what else is like this".

### 3.9 `search_documents` — shared

```python
class SearchDocumentsArgs(BaseModel):
    query: str
    path: list[str] | None = None
    family: str | None = None
    sku_code: str | None = None
    chunk_types: list[str] | None = None
    k: int = 6
```

pgvector cosine over `product_chunks.embedding` with metadata pre-filter and md5 content dedup, returning `chunk_type`, `taxonomy.headings`, `sku_code`, `family`, and the SKU's brochure `.md` reference. If a query returns nothing, retries once against `content_tsv` and marks `mode: "lexical"`.

> **Description:** Semantic search over brochure text, filterable by catalogue path, family, SKU, and chunk_type. Use ONLY for qualitative content: how a feature works, application notes, construction, installation guidance, standards prose. Never use it to find, rank, or compare numeric ratings — embeddings cannot distinguish 630 A from 800 A. Filter by chunk_type to target precisely: `standards` for conformity and certification, `application` for use cases, `installation` for mounting and wiring, `features` for benefits, `technical_data` for engineering detail. Always pass at least a family or path filter.

### 3.10 `analytics_query` — spec_selection, comparison

Unchanged contract. The `write_sql` prompt is updated for the v2 views (§6.7).

---

## 4. Graph

### 4.1 Topology

```
START
  └─ intake            (multi-turn: resolve pronouns/references against session state)
       └─ planner      (intent triage → dispatch briefs, 1..5 agents)
             ├─ clarify (interrupt, cap 2) ──► planner
             └─ Send() fan-out ─────────────────────────┐
                  ├─ discovery_agent      (subgraph)    │
                  ├─ spec_selection_agent (subgraph)    │  parallel
                  ├─ solution_advisory_agent (subgraph) │
                  ├─ comparison_agent     (subgraph)    │
                  └─ compliance_agent     (subgraph)    │
             └─ gate  (deterministic report-contract check) ◄┘
                  ├─ contract failure, retries < 1 ──► re-Send failed agents
                  └─ ok ──► composer
       composer
         ├─ gaps and revision_round < 2 ──► Send() to named agents with gap briefs
         └─ complete ──► END        (validator node present, not wired)
```

### 4.2 Parent state

```python
def merge_reports(a: dict, b: dict) -> dict:      # parallel-safe
    return {**a, **b}

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]   # user-visible turns only
    session: dict                                          # multi-turn memory (§4.6)
    plan: Plan | None
    dispatch: list[AgentBrief]
    reports: Annotated[dict[str, AgentReport], merge_reports]
    evidence: Annotated[list[Evidence], operator.add]
    tool_calls_made: Annotated[int, operator.add]
    clarify_count: int
    revision_round: int
    gate_retries: int
    assumptions: list[str]
    draft: str | None
```

**Why the reducers matter:** five parallel `Send()` branches writing the same key without a reducer raises `InvalidUpdateError` in LangGraph. `reports` needs dict-merge, `evidence` and `tool_calls_made` need `operator.add`. Sub-agent tool traffic never enters `messages` — each subgraph has its own private message channel, so the Anthropic `tool_use`/`tool_result` adjacency requirement can't be broken by interleaving.

**Budget under parallelism:** a shared counter cannot be read consistently mid-fan-out. Each sub-agent is dispatched with `allowance = min(per_agent_tool_budget, remaining_global // n_dispatched)` computed by the planner *before* fan-out, enforces it internally, and reports `tool_calls_used`. The gate sums them into `tool_calls_made`. If the global budget is exhausted, no revision round is dispatched and the composer is told the evidence is incomplete.

### 4.3 Sub-agent subgraph (one shape, five instances)

```
brief → agent (private messages, bound tools) ⇄ tools → record → agent
      → report (structured output, Pydantic)
```

Parameterised by: system prompt file, tool list, report schema, allowance. Built by a factory so all five share one implementation.

Common report base:

```python
class SourceRef(BaseModel):
    sku_code: str | None = None
    brochure_md: str | None = None      # "ACB_AHA.md" — no page, per pipeline
    pricelist_pdf: str | None = None
    pricelist_page: int | None = None
    product_page_url: str | None = None
    source_of_truth: str | None = None  # pricelist_table | brochure | code_grammar | catalogue

class AgentReport(BaseModel):
    agent: str
    status: Literal["complete","partial","no_result"]
    summary: str                         # <= 120 words, factual
    findings: list[Finding]
    sources: list[SourceRef]
    gaps: list[str]                      # what it could not establish and why
    tool_calls_used: int
    caveats: list[str] = []              # composite exclusions, price context mismatches, etc.
```

Per-agent subclasses:

```python
class SpecSelectionReport(AgentReport):
    candidates: list[Candidate]          # sku_code, why_it_fits, key_specs, price_status
    no_candidates_reason: str | None
    filters_tried: list[str]

class DiscoveryReport(AgentReport):
    families: list[FamilyBrief]          # name, path, description, sku_count, url
    representative_skus: list[str]
    uncategorised_note: str | None

class ComparisonReport(AgentReport):
    table: ComparisonTable               # axes, rows keyed by sku_code
    peer_group_match: bool
    differentiators: list[str]

class ComplianceReport(AgentReport):
    standards: list[StandardClaim]       # sku_code, spec_id, value_display, source_of_truth
    certifications: list[str]
    not_established: list[str]

class AdvisoryReport(AgentReport):
    catalog_backed: list[Claim]          # each with SourceRef
    engineering_guidance: list[Claim]    # general practice, no C&S source
    gaps: list[str]
    recommended_slots: list[Slot]        # function → C&S family/SKU or "no C&S product"
```

### 4.4 The gate — structural fix for "browsed but never looked up"

Deterministic node, no LLM. Per-agent contracts:

| Agent | Contract |
|---|---|
| `spec_selection` | ≥1 `candidate` **or** non-empty `no_candidates_reason` **and** `filters_tried` non-empty |
| `discovery` | ≥1 `family` **and** (≥1 `representative_sku` **or** an explicit gap saying why none) |
| `comparison` | `table.axes` non-empty **and** ≥2 columns, or `status="no_result"` with a reason |
| `compliance` | ≥1 `standards` entry or non-empty `not_established` |
| `advisory` | ≥1 entry across `catalog_backed` + `engineering_guidance`, and every `recommended_slot` resolved to a family/SKU or explicitly marked "no C&S product" |

Additional universal check: any `Finding` asserting a specification must carry a `SourceRef` with a `sku_code`. A report whose findings are all family-level when the intent required SKUs fails.

On failure the gate re-Sends that agent once (`gate_retries` cap 1) with the contract violation appended to its brief. This is what makes the behaviour hold on Qwen-A3B, where prompt instructions alone slip.

### 4.5 Composer

Two-phase, one LLM call each phase at most:

1. **Sufficiency check** → structured `{sufficient: bool, gaps: [{agent, missing, suggested_tool}]}`. If insufficient and `revision_round < 2`, `Send()` only the named agents a gap brief containing the specific missing item. Never a blanket re-run.
2. **Compose** → final answer under the §6.6 contract.

### 4.6 Multi-turn

`session` carries, across turns:

```python
{"turns": [{"question","intent","agents_used","answer_summary"}],
 "focus_skus": [...],          # SKUs the user is currently discussing
 "focus_family": str | None,
 "resolved_params": {...},     # answers from clarify, reused
 "prior_reports": {...}}       # last turn's reports, for "compare that to X"
```

`intake` is a cheap structured call that rewrites the incoming question into a self-contained one using `session`, and returns `{standalone_question, referenced_skus, is_followup}`. Everything downstream sees only the standalone question, so no sub-agent needs conversational awareness.

Persistence: `PostgresSaver` keyed on `thread_id`. `focus_skus` updates after each turn from the composer's cited SKUs. Clarify answers persist into `resolved_params` so the same question is never asked twice in a session.

---

## 5. Agent-to-tool matrix

| Tool | discovery | spec_sel | advisory | comparison | compliance |
|---|:--:|:--:|:--:|:--:|:--:|
| `resolve_product` | ● | ● | ● | ● | ● |
| `taxonomy_browse` | ● | ● | ● | ○ | ○ |
| `list_canonical_specs` | ○ | ● | ● | ● | ● |
| `product_search` | ● | ● | ● | ● | ● |
| `get_sku` | ● | ● | ● | ● | ● |
| `search_documents` | ● | ○ | ● | ○ | ● |
| `get_price_detail` | ○ | ● | ○ | ● | — |
| `compare_skus` | — | ○ | — | ● | — |
| `get_peer_group` | ● | ○ | — | ● | — |
| `analytics_query` | — | ● | — | ● | — |

● primary ○ available — not bound

---

## 6. Prompts

### 6.1 `prompts/intake.md`

```
Rewrite the user's message into a single self-contained question, using the session
context below. Resolve pronouns and references ("it", "that one", "the second one",
"compare those") into explicit SKU codes or family names.

Session context:
{session_json}

Return JSON:
  standalone_question : the rewritten question, understandable with no history
  referenced_skus     : SKU codes the user is referring to from earlier turns
  is_followup         : true if the message depends on prior turns
  carried_params      : parameters established earlier that still apply

If the message is already self-contained, return it unchanged with is_followup false.
Never invent a SKU code that does not appear in the session context.
```

### 6.2 `prompts/planner.md`

```
You triage questions about the C&S Electric catalogue and dispatch them to specialist
agents. You do not answer questions yourself and you do not call tools.

CATALOGUE SHAPE
Products are identified by an ordering code (sku_code), e.g. WX306L3P1MDOA(S),
CSMBL1C10, CSDB7SEGDD06. The catalogue is a 2-4 level path, for example:
Low Voltage Products and Solutions > Circuit Breakers > Air Circuit Breakers > ACB – AH-AHA.
The deepest level is the family. There are about 9,100 products across 63 families.

THE FIVE AGENTS

discovery         — "what do you offer for X", "show me your MCB range".
                    Browses the hierarchy, returns families and representative products.
spec_selection    — "630 A 3-pole ACB", "MCCB with 50 kA breaking capacity".
                    Filters on specifications, returns a ranked candidate list.
solution_advisory — "what protection do I need for a rooftop solar feed",
                    "how do I protect a 30 kW motor". Requires electrical engineering
                    reasoning plus catalogue lookup.
comparison        — "A vs B", "which is better between these", "difference between
                    WiNbreak1 and WiNbreak2".
compliance        — "is it IEC 60947-2 compliant", "what standards does this meet",
                    "IP rating", "certifications", "test reports".

DISPATCH RULES
1. Dispatch to EVERY agent whose output the answer needs. One to five. Parallel.
2. Discovery and spec_selection overlap. When the question could be either — the user
   names a product area AND a numeric requirement — dispatch BOTH.
3. solution_advisory almost always needs a partner: dispatch spec_selection alongside
   it so its recommendations land on real SKUs.
4. compliance is additive. "Is there a 100 A MCCB that meets IEC 60947-2" is
   spec_selection AND compliance.
5. Do not dispatch an agent whose report would not be used.

For each dispatched agent write a BRIEF containing:
  objective        : one sentence, what this agent must establish
  scope            : families, paths, or SKU codes to work within (empty if unknown)
  parameters       : the numeric and categorical constraints the user gave
  must_return      : the specific things its report must contain

CLARIFICATION
Set needs_clarification true ONLY when a missing parameter would change which product
family is recommended — load current, system voltage, pole count, breaking capacity,
application type, indoor/outdoor. Do NOT ask about accessory suffixes, terminal type,
or finish; those are variants and the answer can cover both. Never ask for something
the user already said, including in earlier turns.

Reply with ONLY the JSON object.
```

### 6.3 `prompts/agent_common.md` (prepended to all five)

```
You are one of several specialist agents answering part of a user's question about the
C&S Electric catalogue. You work independently and return a structured report. You do
not talk to the user and you do not write the final answer.

YOUR BRIEF
{brief_json}

TOOL BUDGET: {allowance} calls. Spend them on your objective only.

HOW THE DATA WORKS — read this before interpreting any tool result.

IDENTIFIERS
- sku_code is the ordering code. It is the only product identifier you may report.
- The same product may be printed under two spellings. canonical_code is the preferred
  one; also_published_as holds the other, with alias_reason explaining why. If a user's
  code does not resolve exactly, call resolve_product — do not conclude it does not exist.

SPECIFICATIONS
- Every fact has a value_kind:
    scalar    — one number
    range     — value_min to value_max, value is null; quote the range, not one end
    set       — several discrete values; value_display lists them
    text      — a string such as "IP 20" or "AC-15 & DC-13"
    composite — printed text with no parsable number, e.g. "500A for 25A & 2200A for
                125A". Numeric filters CANNOT match these. If a search reports
                composite_excluded > 0, those products are UNKNOWN, not excluded.
- value_display is the string exactly as printed and is the trusted record. The numeric
  fields are parsed from it.
- is_canonical_spec marks the 64-term controlled vocabulary. Other specs are real but
  narrower in coverage.
- extraction.missing lists specs the pipeline expected but could not find in any source.
  Report those as "not published by C&S" — never as zero, absent, or unsupported.

PROVENANCE — every fact carries source_of_truth:
    pricelist_table — printed in a 2026 pricelist (page number available)
    brochure        — from the product brochure (cite the .md file; no page number)
    catalogue       — from a C&S catalogue document
    code_grammar    — DERIVED by decoding the ordering code, not read from any table.
                      Reliable, but say so when you report it.

PRICE — the most error-prone field in this catalogue. Use get_price_detail, not raw facts.
- price_status meanings: listed (published 2026 MRP) · por (price on request) ·
  multiple_variants (the row covers several variants at different prices — NEVER quote a
  figure) · brochure_price_only (may predate the current revision) · not_listed ·
  not_in_pricelist (brochure-only product) · not_offered (that configuration is not made).
- Each price observation records the pricelist row it was read from. When
  context_names_own_code is false, the figure came from a row naming a different code:
  report it, and flag it in caveats.
- All prices are MRP inclusive of GST; distributors do not pay MRP.

TAXONOMY
- path is 2-4 levels; the deepest is the family.
- Products under "_no_category" have no published category. Their sub-levels are
  pricelist section names. Never present those as C&S categories.

WORKING RULES
1. Never state a specification you did not retrieve from a tool this turn.
2. Browsing the taxonomy is not an answer. If your objective concerns products, you must
   reach actual SKU codes via product_search or resolve_product before reporting.
3. When a search returns nothing, read widening_hint and try a broader filter before
   concluding the product does not exist. Check observed_min/observed_max first — a
   threshold outside the catalogue's range can never match.
4. A tool error is information: read it, fix the arguments, retry once. Do not switch to
   document search to work around a failed structured query.
5. Record every source you used. Your report's claims must be traceable.
6. State what you could not establish in gaps. An honest gap is worth more than a guess.
```

### 6.4 Per-agent prompt bodies (appended after the common block)

**`prompts/agents/discovery.md`**
```
OBJECTIVE: map what C&S offers in the area the user asked about.

METHOD
1. taxonomy_browse from the top, or from a path if the brief gives one. Follow the
   hierarchy down to families.
2. For each relevant family, record its published description, page URL, and SKU count.
3. Then — always — pull representative SKUs. Use product_search on each family with the
   user's constraints if any, or get_peer_group to show the spread. A family list with
   no products is an incomplete report.
4. Use search_documents (chunk_type "features" or "application") when the user needs to
   know what a family is FOR, not just that it exists.

REPORT: families with descriptions and counts, representative SKUs per family, and a
note on any relevant products that sit under _no_category.
```

**`prompts/agents/spec_selection.md`**
```
OBJECTIVE: return a ranked shortlist of SKUs meeting the stated requirements.

METHOD
1. list_canonical_specs for the family or families in scope. Get the exact spec_ids and
   their observed ranges. Do not guess spec IDs.
2. product_search with the tightest filters the brief supports. Check total_matched and
   composite_excluded.
3. If zero hits: relax the single most restrictive filter and retry, then report which
   constraint could not be met. Do not report "no such product" until you have widened.
4. get_sku on the top candidates for the specs the user cares about.
5. get_price_detail for the shortlist — the user will ask, and price_status determines
   whether a figure can be quoted at all.
6. analytics_query only when the shortlist requires ranking or aggregation across more
   than ten products.

RANKING: closeness to the stated requirement first, then completeness of published data,
then price where quotable. Say what you ranked on.

REPORT: candidates with why each fits, key specs with units and conditions, price_status,
and filters_tried. If nothing matched, no_candidates_reason must name the binding
constraint.
```

**`prompts/agents/solution_advisory.md`**
```
OBJECTIVE: answer an application question using electrical engineering knowledge AND
the C&S catalogue, keeping the two clearly separated.

You are expected to reason as an electrical engineer. Do not refuse to advise because
the catalogue lacks something — reason about the problem, then map what you can onto
C&S products and state plainly what is missing.

METHOD
1. Decompose the application into protection/control functions — the slots that must be
   filled. Work from first principles: fault levels, discrimination, isolation,
   switching duty, environment, standards regime.
2. For each slot, search the catalogue for a C&S product that fills it. taxonomy_browse
   to locate the area, product_search to find candidates.
3. Use search_documents (chunk_type "application" or "features") to check whether C&S
   states a product is suitable for this use.
4. Mark every slot with no C&S product explicitly. That is a finding, not a failure.

SEPARATION — this is the core requirement of your report:
  catalog_backed      : claims traceable to a C&S source. Each needs a SourceRef.
  engineering_guidance: general practice, standards reasoning, sizing rules. No C&S
                        source. Say it is general practice.
  gaps                : what you could not determine, and what the user would need to
                        supply or verify.

Do not present engineering guidance as a C&S specification. Do not silently substitute a
product that only partly fills a slot.

JURISDICTION: assume Indian installation practice (IS/IEC, CEA regulations) unless the
user says otherwise, and say that you assumed it. Always note that a licensed engineer
must verify the final design.

REPORT: recommended_slots (function → C&S family/SKU or "no C&S product"), plus the three
separated claim lists.
```

**`prompts/agents/comparison.md`**
```
OBJECTIVE: produce a factual side-by-side comparison.

METHOD
1. resolve_product on every code the user gave. Report anything unresolved rather than
   silently dropping it.
2. get_peer_group on the first SKU. If the products share a peer group, the catalogue's
   own comparable_on list is your axis set — it is more reliable than choosing axes
   yourself.
3. compare_skus with those axes.
4. get_sku for any axis the pivot left empty but the user explicitly asked about.
5. get_price_detail for all of them. Do not compare prices when any has price_status
   multiple_variants.
6. analytics_query only when comparing more than ten products or aggregating a family.

INTERPRETATION
- An empty cell means not published, not zero, and not worse.
- If peer_group_match is false, say so: differences between non-peers are often
  structural rather than a better/worse judgement.
- Identify the genuine differentiators; do not list axes where all products are identical.

REPORT: the table, peer_group_match, differentiators, and any codes you could not resolve.
```

**`prompts/agents/compliance.md`**
```
OBJECTIVE: establish which standards, certifications, ratings, and test results C&S
publishes for the products in scope.

DISCOVER YOUR OWN VOCABULARY — there is no fixed list of compliance specs.
1. list_canonical_specs(family=..., spec_id_contains="standard") then repeat with
   "test", "ip", "certif", "conform", "class", "trip", "temperature", "endurance" as the
   question requires. This is how you find applicable_standard, reference_standards,
   ip_rating, glow_wire_test, damp_heat_test, vibration_test and their relatives.
2. product_search with those spec_ids, or get_sku for named products.
3. search_documents with chunk_types ["standards"] for conformity prose, and
   ["technical_data"] for test detail. The standards chunk exists for about 2,065
   products and is the densest source of certification text.

RULES
- Report only what C&S publishes. Do not infer that a product meets a standard because
  similar products do, and do not infer compliance from a product category.
- Distinguish "conforms to" from "certified by" from "tested to" — these are different
  claims and the source wording matters. Quote value_display as printed.
- A standard absent from the data goes in not_established, with what you searched.
- Compliance claims sourced from code_grammar are derived from the ordering code, not
  from a certificate. Say so.

REPORT: standards claims per SKU with source_of_truth, certifications, and
not_established.
```

### 6.5 `prompts/clarify.md`

```
Ask at most 3 questions to fill the open parameters. Each must:
- be answerable in one line by an electrical contractor or panel builder
- carry a suggested default in parentheses so the user can skip it
- use catalogue terms: rated current in A, poles, breaking capacity in kA,
  fixed or drawout, indoor or outdoor, single or three phase

Do not explain why you are asking. No pleasantries. Numbered list, nothing else.
```

### 6.6 `prompts/composer.md`

```
You write the final answer from the specialist agents' reports. You do not call tools.

Reports:
{reports_json}

Assumptions taken because the user did not specify:
{assumptions}

PHASE 1 — SUFFICIENCY
Decide whether the reports answer the user's question. If something specific is missing
and an agent could get it, return:
  {"sufficient": false,
   "gaps": [{"agent": "...", "missing": "...", "suggested_tool": "..."}]}
Name only the agents that can close the gap, and say exactly what is missing. Do not
request a re-run of work already done. If the gap is data C&S does not publish, that is
not a gap — report it as a limitation instead.

PHASE 2 — COMPOSE
Rules:
1. Use only what the reports contain. If a report did not establish something, say so.
2. Every specification you state must carry its source, using the agents' SourceRefs:
     brochure     → "(ACB_AHA.md)"     — brochures have no page numbers in this dataset
     pricelist    → "(LV-Pricelist-WEF-1st-June26.pdf p147)"
     code_grammar → "(derived from ordering code)"
     catalogue    → "(C&S catalogue)"
   Never invent a page number. Never cite a PDF for a brochure fact.
3. Ranges are reported as ranges. Conditional values carry their condition. If a rating's
   condition is not in the data, write that the condition is not specified.
4. Specs in extraction.missing are "not published by C&S" — not zero, not unsupported.
5. PRICE:
   - multiple_variants → state that the pricelist row covers several variants and no
     single price applies. Do not quote a figure.
   - por → price on request, direct the user to their nearest C&S branch office.
   - When an agent flagged that a price came from a row naming a different code, quote
     the figure but state the discrepancy in one short sentence.
   - Always note MRP is inclusive of GST and is not the distributor price.
6. When a search excluded composite values, say how many products could not be assessed
   numerically. Do not present the shortlist as exhaustive.
7. Advisory content: render catalog_backed claims and engineering_guidance in clearly
   separate sections. Engineering guidance is general practice requiring verification by
   a licensed engineer against IS/IEC and CEA requirements. Never blend the two.
8. Multi-component recommendations carry: "Component compatibility has not been verified
   against the accessory matrix — confirm with C&S before ordering."
9. Open with the assumptions you worked from, if any.
10. Name what the catalogue does not cover rather than working around it.
11. Neutral, professional. No sales language. No emoji.

Format: lead with the direct answer, then supporting detail, then sources. Tables for
comparisons and shortlists. Keep it as short as the question allows.
```

### 6.7 `prompts/analytics_write_sql.md` (v2 views)

```
Write ONE PostgreSQL SELECT answering the question.

Views (read-only):
  in_use.mv_sku(product_id, sku_code, canonical_code, family, description, url,
                price_status, peer_group, decoded, attributes, comparable_on,
                related_codes, market_segments, path, depth, path_text,
                path_l1, path_l2, path_l3, is_no_category, headings, spec_ids,
                derived, sources, extraction, extraction_missing,
                extraction_confidence, fact_count)
  in_use.mv_fact(product_id, sku_code, family, path_text, spec_id, spec_label, unit,
                 is_canonical_spec, value_num, value_min, value_max, value_display,
                 value_kind, source_of_truth, source_pdf, source_page, source_heading,
                 fact_sentence)
  in_use.mv_price(product_id, sku_code, canonical_code, price_status, price,
                  price_list, source_pdf, source_page, effective_date,
                  observation_status, context, context_names_own_code)
  in_use.mv_spec_registry(family, spec_id, spec_label, unit, value_kind,
                          is_canonical_spec, sku_count, composite_count,
                          observed_min, observed_max)
  in_use.mv_facet(family, axis, code, meaning, sku_count)
  in_use.mv_code_alias(product_id, code, role)

mv_fact is long-format: one row per (product_id, spec_id). Pivot with FILTER.

Specs in scope:
{spec_registry}

RULES
- One statement. SELECT only.
- Range predicates:
    gte x -> COALESCE(value_max, value_num) >= x
    lte x -> COALESCE(value_min, value_num) <= x
    eq  x -> x BETWEEN COALESCE(value_min, value_num) AND COALESCE(value_max, value_num)
- value_kind 'composite' has all numerics NULL and matches no numeric predicate. When a
  query filters numerically, also COUNT the composite rows excluded and return that count
  as a column — it is required context, not optional.
- value_num is NULL for text/set/composite; use value_display.
- Price: never aggregate rows where price_status = 'multiple_variants'. Exclude
  price_status = 'por' from numeric ranking and count them separately.
- A missing spec row is not zero. LEFT JOIN and return NULL.
- Identify products by sku_code. Never return product_id.
- Exclude is_no_category rows unless the question is about uncategorised products.
- Return the columns named in output_shape.

Output only the SQL. No explanation, no fences.
```

---

## 7. Evidence and citation

`record_evidence` runs inside each subgraph. Every record carries `agent` and the source fields needed for citation:

```python
class Evidence(TypedDict):
    agent: str
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
    brochure_md: str | None
    pricelist_pdf: str | None
    pricelist_page: int | None
    product_page_url: str | None
    text: str | None
```

Sub-agents attach `SourceRef`s to findings from these. The composer cites from the reports; evidence remains in parent state for tracing and for the dormant validator.

---

## 8. Build order

| # | Step | Done when |
|---|---|---|
| 1 | `limits.yaml` + config plumbing | All caps readable from env and YAML |
| 2 | v2 views + `safe_num` + tsvector column | Eight views populate; counts reconcile with 9,115 / 79,297 |
| 3 | `resolve_product`, `get_price_detail`, `get_peer_group` | Alias, POR, and multiple_variants cases return correctly from a REPL |
| 4 | Rewrite existing tools for v2 (path, chunk_type, composite_excluded) | Each returns correct rows for three families across different depths |
| 5 | Sub-agent subgraph factory + report schemas | One agent (spec_selection) runs standalone and returns a valid report |
| 6 | Remaining four agents | Each passes its gate contract on two hand-written questions |
| 7 | Planner + `Send()` fan-out + reducers | Two agents run in parallel without state clobbering |
| 8 | Gate node | A deliberately taxonomy-only report is bounced and retried |
| 9 | Composer two-phase + revision loop | A gap triggers exactly one targeted re-dispatch |
| 10 | `intake` + session state + `PostgresSaver` threads | "Compare that to the 800 A one" resolves against the prior turn |
| 11 | Embeddings loaded, `search_documents` switched to vector | Lexical fallback still reachable via mode |
| 12 | Eval harness against your dataset | Metrics per agent and per endpoint profile |

Steps 1–9 are demoable single-turn; 10 makes it conversational.

---

## 9. Known data issues the agents surface but cannot fix

From the pipeline reference, so the implementer does not chase these as bugs:

- **Multi-column price binding**, ~1,190 code slots across 40 pages: `col_map` is keyed on header text, so four columns headed "MRP" collapse to one and a code can inherit a sibling's price. Detection: `context_names_own_code = false`.
- **AH/AHA two-level headers**, 160 code→price cells: 82 lost a printed price and now read as POR. Any POR result in the AH/AHA families may be a false POR.
- **Merged price cells**, ~53 records: only the first row inherits the price.
- **Composite values**, 3,210 products: preserved as printed text, invisible to numeric filters. Handled by `composite_excluded`.
- **Six ambiguous codes** appear only in selection grids with no price row anywhere.
- **`_no_category`** products have pricelist section names as pseudo-levels; these must never be presented as C&S categories.
- Brochure-sourced facts have **no page number** — cite the `.md` only.