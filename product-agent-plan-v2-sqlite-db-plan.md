# C&S Product Agent — SQLite Migration Plan (v3)

Amends `product-agent-plan-v2.md`. **Only the data layer and tool internals change.** Graph topology, the five sub-agents, report schemas, the gate node, the composer revision loop, and all prompts except the two in §7 carry over unchanged.

**Decisions locked**

| Decision | Choice |
|---|---|
| Store | All-SQLite. Structured data and chunks/embeddings in one file. |
| Structured grain | One table, one row per (SKU, fact). No helper view, no primary-row marker. |
| SKU-grain reads | `DISTINCT` / `GROUP BY` idioms (§4.1) |
| Taxonomy | Path unnested into fixed level columns, `'N/A'` filler, plus a separate `family` column |
| Source of build | Existing Postgres `mv_*` views |
| Agent access | Read-only |
| Quantization | None for now |
| Factless SKUs | Audited and reported at build time; sentinel rows emitted |

---

## 0. Pre-flight — run before writing any code

Three queries against Postgres. Their answers determine the schema, so they are step zero, not a validation afterthought.

**0.1 Maximum path depth — fixes the number of level columns.**

```sql
SELECT max(jsonb_array_length(taxonomy->'path')) AS max_depth,
       count(*) FILTER (WHERE jsonb_typeof(taxonomy->'path') <> 'array') AS non_array_paths
FROM in_use.product_chunks
WHERE is_active;

-- distribution, and whether _no_category branches run deeper
SELECT taxonomy->'path'->>0 AS l1,
       jsonb_array_length(taxonomy->'path') AS depth,
       count(DISTINCT product_id) AS skus
FROM in_use.product_chunks
WHERE is_active AND jsonb_typeof(taxonomy->'path') = 'array'
GROUP BY 1, 2 ORDER BY 2 DESC, 3 DESC;
```

Sample data shows depths 2, 3 and 4. Create exactly `max_depth` level columns — no more, no fewer. If `_no_category` runs deeper than the published branches, decide whether to truncate it or size for it before building, because widening the table later means a full rebuild.

**0.2 Fact volume and width — confirms the size projection.**

```sql
SELECT count(*) AS fact_rows,
       count(DISTINCT sku_code) AS skus,
       round(avg(cnt), 1) AS mean_facts_per_sku,
       max(cnt) AS max_facts_per_sku
FROM (SELECT sku_code, count(*) AS cnt FROM in_use.mv_fact GROUP BY sku_code) t;
```

Projection from the sample is ~207k rows at ~520 MB. If `mean_facts_per_sku` comes back much above 23, revisit whether the heavy JSON arrays should repeat on every row.

**0.3 `sqlite-vec` loadability on the target machine.**

```python
import sqlite3, sqlite_vec
c = sqlite3.connect(":memory:")
c.enable_load_extension(True)          # AttributeError on Pythons built without extension support
sqlite_vec.load(c)
print(c.execute("select vec_version()").fetchone())
```

If this fails, the extension is unavailable and the chunk table moves to Postgres (§1.3) — a decision worth making before the build script exists rather than after.

---

## 1. Vector search

### 1.1 Design

No `vec0` virtual table. Embeddings are `BLOB` on the `chunk` table; distance comes from sqlite-vec's scalar function over an already-filtered set:

```sql
SELECT chunk_id, sku_code, chunk_type, content, brochure_md,
       vec_distance_cosine(embedding, :qvec) AS dist
FROM chunk
WHERE family LIKE :family
  AND chunk_type IN ('standards','technical_data')
  AND embedding IS NOT NULL
ORDER BY dist
LIMIT :k;
```

`vec0`'s KNN runs before unrelated predicates, so a filtered `vec0` query returns the global nearest neighbours intersected with the filter — usually nothing. Its metadata columns also support only `=`, `!=`, `<`, `>`, `<=`, `>=`, `BETWEEN`, and our tools filter with `LIKE`. The scalar-function path keeps ordinary SQL semantics: filter first, rank the survivors.

### 1.2 Cost and the enforced filter

Brute force over survivors. A family filter leaves 10²–10³ chunks → low single-digit ms. Unfiltered would be 79,297 × 768 ≈ 61M FLOPs → 0.5–2 s. So `search_documents` **rejects a call with no `family`, `path`, or `sku_code` filter**, returning an error that names the required argument. The v2 tool description already instructs this; now it is enforced in code.

### 1.3 When to move chunks to Postgres instead

All-SQLite is the recommendation because the only capability Postgres adds here is an ANN index, which matters only for the unfiltered searches the tools don't perform. Revisit if any of these become true:

- unfiltered semantic search becomes a genuine requirement
- chunk count passes ~250k (filtered candidate sets grow with it)
- `sqlite-vec` cannot be loaded on the deployment target (§0.3)

The migration is contained: `chunk` moves to Postgres with pgvector + HNSW, `search_documents` switches connection, and nothing else changes — **provided** `chunk_types` stays denormalized onto the structured table (§3.1), which removes the only tool that would otherwise need both stores in one query.

### 1.4 Lexical fallback

`chunk_fts` (FTS5) backs `search_documents` when embeddings are absent — they are NULL today — or when a vector query returns nothing. The result reports `mode: vector | lexical`.

---

## 2. Build artifact

### 2.1 Pipeline

```
Postgres pipeline → product_chunks → mv_* views → build_sqlite.py → catalog-<date>.sqlite
```

Build from the **existing views**, not raw `product_chunks`. They already resolve the polymorphic `fact.source`, the source-string regexes, and the price-context matching — none of which SQLite can express, since it has no `regexp_replace`, no `~`, no `mode() WITHIN GROUP`, and no materialized views.

The `.sqlite` file is immutable and read-only in production. LangGraph checkpoints go in a **separate** file (`checkpoints.sqlite`) so the catalogue can be versioned and swapped without touching conversation state.

### 2.2 `scripts/build_sqlite.py`

```
1  connect Postgres; assert mv_* row counts reconcile against product_chunks
2  read max path depth (§0.1); assert it matches the compiled-in column count
3  stream mv_sku ⋈ mv_fact ⋈ mv_price ⋈ mv_source → sku_fact rows
4  stream product_chunks → chunk rows
5  run audits (§2.3); write build_report.json
6  create indexes, FTS5, build_meta; ANALYZE; VACUUM
```

Python does the flattening: JSON serialisation, price summarisation, `'N/A'` padding, `chunk_types` rollup, sentinel emission. All unit-testable.

### 2.3 Build audits

`build_report.json`, plus a non-zero exit on the first three:

| Audit | Action |
|---|---|
| **SKUs with zero facts** | **listed with `sku_code`, `family`, `path_text`, counted; sentinel rows emitted; exit 2** |
| Path depth exceeds the compiled column count | hard fail |
| `sku_code` not unique per `product_id` | hard fail |
| Alias collisions (one code → two products) | listed, warn |
| `value_kind = 'composite'` | counted per family, warn |
| `context_names_own_code = false` | counted, listed by SKU, warn |
| SKUs under `_no_category` | counted, warn |
| Chunks with NULL embedding | counted; lexical-only mode flagged in `build_meta` |

The factless-SKU audit is the discovery step you asked for. Those SKUs still receive one row (`is_sentinel = 1`, fact columns NULL) so they stay visible to `taxonomy_browse` and `product_search` — at this grain, a SKU with no facts would otherwise have no row at all and vanish from the catalogue.

---

## 3. Schema

### 3.1 `sku_fact` — the single structured table

One row per (SKU, fact). ~207,000 rows, ~520 MB. All SKU metadata repeats on every row.

Level columns below assume `max_depth = 5`; **set the real count from §0.1 before building.**

```sql
CREATE TABLE sku_fact (
  row_id                INTEGER PRIMARY KEY,
  is_sentinel           INTEGER NOT NULL,   -- 1 = SKU has no facts; fact columns NULL

  -- identity
  sku_code              TEXT NOT NULL,
  canonical_code        TEXT NOT NULL,
  product_id            INTEGER,
  family                TEXT NOT NULL,      -- always the leaf; NOT positional
  description           TEXT,
  url                   TEXT,

  -- taxonomy, unnested; 'N/A' where the branch is shallower
  division              TEXT NOT NULL DEFAULT 'N/A',   -- level 1
  product_group         TEXT NOT NULL DEFAULT 'N/A',   -- level 2
  product_subgroup      TEXT NOT NULL DEFAULT 'N/A',   -- level 3
  product_range         TEXT NOT NULL DEFAULT 'N/A',   -- level 4
  product_series        TEXT NOT NULL DEFAULT 'N/A',   -- level 5
  path_depth            INTEGER NOT NULL,
  path_text             TEXT NOT NULL,
  is_no_category        INTEGER NOT NULL,

  -- commercial
  price_status          TEXT,
  price_quotable        INTEGER,            -- 0 when multiple_variants, or all observations mismatch
  price_inr             REAL,               -- best listed observation, else NULL
  price_list            TEXT,
  price_source_pdf      TEXT,
  price_source_page     INTEGER,
  price_effective_date  TEXT,
  price_context_ok      INTEGER,            -- 0 = observation row named a different code
  price_observations    TEXT,               -- JSON array, all observations

  -- relationships and decode
  peer_group            TEXT,
  comparable_on         TEXT,               -- JSON array
  related_codes         TEXT,               -- JSON array
  also_published_as     TEXT,               -- JSON array
  alias_reason          TEXT,
  decoded               TEXT,               -- JSON object
  attributes            TEXT,               -- JSON object
  market_segments       TEXT,               -- JSON array
  market_segments_text  TEXT,               -- 'Commercial|Residential', for LIKE

  -- provenance and coverage
  brochure_md           TEXT,               -- e.g. 'ACB_AHA.md'; no page, by design
  product_page_url      TEXT,
  pricelist_refs        TEXT,               -- JSON [{pdf,page}]
  sources               TEXT,               -- JSON array, raw
  headings              TEXT,               -- JSON array
  spec_ids              TEXT,               -- JSON array
  chunk_types           TEXT,               -- JSON array; which chunk types exist for this SKU
  extraction_missing    TEXT,               -- JSON array
  extraction_confidence TEXT,
  fact_count            INTEGER NOT NULL,
  derived               TEXT,               -- JSON object

  -- the fact (NULL on sentinel rows)
  fact_id               TEXT,
  spec_id               TEXT,
  spec_label            TEXT,
  unit                  TEXT,
  is_canonical_spec     INTEGER,
  value_num             REAL,
  value_min             REAL,
  value_max             REAL,
  value_display         TEXT,
  value_kind            TEXT,               -- scalar|range|set|text|composite
  source_of_truth       TEXT,               -- pricelist_table|brochure|catalogue|code_grammar
  fact_source_pdf       TEXT,
  fact_source_page      INTEGER,
  fact_source_heading   TEXT,
  fact_sentence         TEXT
);
```

Indexes:

```sql
CREATE INDEX ix_sf_sku_row     ON sku_fact(sku_code, row_id);   -- powers the MIN(row_id) idiom
CREATE INDEX ix_sf_spec_value  ON sku_fact(spec_id, value_num);
CREATE INDEX ix_sf_family_spec ON sku_fact(family, spec_id);
CREATE INDEX ix_sf_family      ON sku_fact(family);
CREATE INDEX ix_sf_levels      ON sku_fact(division, product_group, product_subgroup);
CREATE INDEX ix_sf_value_kind  ON sku_fact(value_kind);
CREATE INDEX ix_sf_price       ON sku_fact(price_status);
CREATE INDEX ix_sf_canonical   ON sku_fact(canonical_code);
```

`ix_sf_sku_row` is the important one — it makes the SKU-grain idiom in §4.1 an index-only scan.

**Level column semantics.** Positional, not semantic; the hierarchy is not uniform across branches. Because the leaf level *is* the family, `product_subgroup` holds the family for depth-3 branches and `product_range` for depth-4 branches. That duplication is intended. **Always filter families on `family`, never on a level column.**

**`chunk_types`** is rolled up at build time so `product_search(has_chunk_type=…)` never needs the chunk table. It is also what keeps the Postgres-for-chunks escape hatch (§1.3) cheap.

### 3.2 `chunk`

```sql
CREATE TABLE chunk (
  chunk_id         INTEGER PRIMARY KEY,
  product_id       INTEGER,
  sku_code         TEXT NOT NULL,
  family           TEXT NOT NULL,
  division         TEXT NOT NULL DEFAULT 'N/A',
  product_group    TEXT NOT NULL DEFAULT 'N/A',
  product_subgroup TEXT NOT NULL DEFAULT 'N/A',
  product_range    TEXT NOT NULL DEFAULT 'N/A',
  product_series   TEXT NOT NULL DEFAULT 'N/A',
  path_text        TEXT NOT NULL,
  chunk_type       TEXT NOT NULL,
  headings         TEXT,            -- JSON array
  content          TEXT NOT NULL,
  content_hash     TEXT NOT NULL,   -- md5, for query-time dedup
  content_len      INTEGER NOT NULL,
  brochure_md      TEXT,
  embedding        BLOB             -- float32[768], NULL until loaded
);

CREATE INDEX ix_ch_family_type ON chunk(family, chunk_type);
CREATE INDEX ix_ch_sku         ON chunk(sku_code);
CREATE INDEX ix_ch_type        ON chunk(chunk_type);
CREATE INDEX ix_ch_hash        ON chunk(content_hash);
CREATE INDEX ix_ch_levels      ON chunk(division, product_group, product_subgroup);

CREATE VIRTUAL TABLE chunk_fts USING fts5(
  content, content='chunk', content_rowid='chunk_id', tokenize='porter unicode61'
);
```

Level columns are duplicated here too, so `search_documents` never joins.

### 3.3 `build_meta`

One row: source database, `mv_*` counts, build timestamp, artifact version, embedding model name and dimension, max observed path depth, audit summary, `embeddings_loaded` flag. Read at startup; the embedding dimension is asserted against the configured query embedder before any search runs.

---

## 4. Tool implementations

`backends/sqlite.py` implements the existing `CatalogBackend` protocol. **Tool signatures, descriptions, and report schemas are unchanged from v2** — only the SQL beneath them.

### 4.1 SKU-grain idioms — read this before writing any tool

The table's grain is the fact, so every SKU-level read must collapse ~23 rows per product. Three canonical patterns; nothing else should appear in the codebase.

**Count products:**
```sql
SELECT count(DISTINCT sku_code) FROM sku_fact WHERE family = :f;
```

**List products with full metadata** — do *not* write `SELECT DISTINCT` over the wide column list; that forces a sort or hash across multi-KB JSON blobs over 207k rows.
```sql
SELECT * FROM sku_fact
WHERE row_id IN (SELECT min(row_id) FROM sku_fact
                 WHERE family = :f GROUP BY sku_code);
```
The inner query is an index-only scan on `ix_sf_sku_row`.

**Aggregate over products, not rows:**
```sql
SELECT division, count(DISTINCT sku_code) AS skus
FROM sku_fact WHERE division <> 'N/A' GROUP BY division;
```

> **The single most likely bug in this design** is a query counting `sku_fact` rows and reporting ~23× the true product count. It belongs in the tool unit tests and is called out in the analytics prompt (§7.2).

### 4.2 `resolve_product` — rapidfuzz, not pg_trgm

SQLite has no `similarity()`. At startup, load the alias list into memory:

```sql
SELECT sku_code, canonical_code, also_published_as
FROM sku_fact
WHERE row_id IN (SELECT min(row_id) FROM sku_fact GROUP BY sku_code);
```

Expand to ~9,700 (code, sku_code, role) entries. Cascade unchanged: exact match on a normalised form (case, spaces, hyphens stripped) → `rapidfuzz.process.extract` with `WRatio`, cutoff 70 → FTS5 over `description` and `chunk.content`. Sub-10 ms at this size, and better ranked than trigram overlap. Still returns `resolution`, `match_role`, `score`, `alias_note`.

### 4.3 `taxonomy_browse`

Walks level columns, treating `'N/A'` as absent:

```sql
SELECT product_group AS node, count(DISTINCT sku_code) AS sku_count
FROM sku_fact
WHERE division = :l1 AND product_group <> 'N/A'
GROUP BY product_group ORDER BY sku_count DESC;
```

At leaf level it returns families plus decoded facet axes via `json_each(decoded)`. `_no_category` rows go in a separate `uncategorised` block, never presented as a category.

### 4.4 `product_search`

Multi-filter matching at fact grain is `GROUP BY … HAVING`:

```sql
WITH matched AS (
  SELECT sku_code FROM sku_fact
  WHERE (spec_id = :s1 AND COALESCE(value_max, value_num) >= :v1)
     OR (spec_id = :s2 AND :v2 BETWEEN COALESCE(value_min, value_num)
                                   AND COALESCE(value_max, value_num))
  GROUP BY sku_code
  HAVING count(DISTINCT spec_id) = :n_filters
)
SELECT sf.* FROM sku_fact sf
JOIN matched m ON m.sku_code = sf.sku_code
WHERE sf.row_id IN (SELECT min(row_id) FROM sku_fact GROUP BY sku_code)
  AND sf.family LIKE :family
LIMIT :limit;
```

`has_chunk_type` filters on the denormalized `chunk_types` array via `json_each`. `composite_excluded` is a second query counting SKUs holding the filtered `spec_id` with `value_kind = 'composite'` — mandatory in the response envelope whenever a numeric filter runs.

### 4.5 `list_canonical_specs`

Replaces `mv_spec_registry` with a runtime `GROUP BY family, spec_id`, `@lru_cache`d per family. `mode() WITHIN GROUP` becomes `MIN(spec_label)` — labels are near-constant within a spec, and picking a real one beats implementing a mode function. `FILTER` is supported in SQLite 3.30+, so `composite_count` carries over. `sku_count` must be `count(DISTINCT sku_code)`.

### 4.6 `get_price_detail`

Reads the summary columns and `json(price_observations)` from any one row of the SKU. `price_quotable` and `price_context_ok` are precomputed at build time, so the composer's disclosure rule is driven by a stored boolean rather than runtime string matching.

### 4.7 `search_documents`

Per §1. Rejects unfiltered calls. Dedups on `content_hash`. Returns `mode`, `shared_by_sku_count`, and the SKU's `brochure_md` for citation.

### 4.8 `analytics_query`

Same subgraph, SQLite dialect. Prompt in §7.2.

---

## 5. Runtime configuration

```yaml
# config/limits.yaml  (additions)
sqlite_path: artifacts/catalog-latest.sqlite
checkpoint_path: state/checkpoints.sqlite
sqlite_pragmas:
  journal_mode: WAL
  query_only: 1
  mmap_size: 268435456
  cache_size: -64000
  temp_store: MEMORY
```

`CS_BACKEND=sqlite|postgres|fixtures`. Keep the Postgres backend working for the parity run (§8, step 10).

Connections: one read-only connection **per thread** (`check_same_thread=False`, thread-local pool), with `sqlite_vec.load(conn)` at open. Five sub-agents run in parallel, so a single shared connection will serialise them or error.

Checkpointer: `SqliteSaver` on the separate file.

---

## 6. Size

| Component | Size |
|---|---|
| `sku_fact` (~207k rows, metadata repeated) | ~520 MB |
| `chunk` content | ~40 MB |
| Embeddings (79,297 × 768 × 4 B) | ~243 MB |
| FTS5 + indexes | ~80 MB |
| **Total** | **~880 MB** |

Acceptable for a local read-only artifact. Two levers if it becomes a distribution problem: int8 quantization (243 → 61 MB, small recall loss) and dropping the heaviest repeated arrays (`related_codes`, `sources`, `price_observations`) from non-first rows.

Every fact correction is a ~23-row update. Irrelevant while the artifact is rebuilt wholesale; it becomes a real cost the day incremental updates are wanted.

---

## 7. Prompt deltas

Everything in v2 §6 carries over except the following two.

### 7.1 `prompts/agent_common.md` — replace the TAXONOMY block

```
TAXONOMY
- The catalogue hierarchy is unnested into fixed columns: division, product_group,
  product_subgroup, product_range, product_series. Branches vary in depth; unused
  levels hold the literal string 'N/A', which means "this branch has no such level" —
  not missing data.
- The deepest level of a path IS the family, so the family name also appears in
  product_subgroup or product_range depending on how deep that branch runs. Always
  filter families on the `family` column, never on a level column.
- Products under division '_no_category' have no published category; their lower levels
  are pricelist section names. Never present those as C&S categories.
```

### 7.2 `prompts/analytics_write_sql.md` — full replacement

```
Write ONE SQLite SELECT answering the question.

Tables:
  sku_fact — ONE ROW PER (sku_code, spec_id). A product with 23 specifications occupies
             23 rows, and ALL of its metadata (family, path, price, decode) repeats
             identically on every one of them. Rows with is_sentinel = 1 are SKUs that
             have no facts at all; their spec columns are NULL.
  chunk    — brochure text, one row per (sku_code, chunk_type).

Key columns:
  sku_code, canonical_code, family, division, product_group, product_subgroup,
  product_range, product_series, path_depth, path_text, is_no_category,
  price_status, price_quotable, price_inr, price_context_ok,
  spec_id, spec_label, unit, value_num, value_min, value_max, value_display,
  value_kind, is_canonical_spec, source_of_truth, fact_sentence

COUNTING PRODUCTS — read this first.
  Never write count(*) to count products. It counts fact rows and overstates by roughly
  23x. Use count(DISTINCT sku_code).
  To list products with their metadata, collapse to one row per product:
     WHERE row_id IN (SELECT min(row_id) FROM sku_fact GROUP BY sku_code)
  Do not use SELECT DISTINCT across the wide column list; it is slow on this table.

DIALECT
- SQLite, not PostgreSQL. FILTER is supported. There is no mode(), no regexp_replace,
  no array type, and no ILIKE (LIKE is already case-insensitive for ASCII).
- JSON columns (decoded, comparable_on, related_codes, market_segments,
  price_observations, spec_ids, chunk_types, extraction_missing) are TEXT. Read with
  json_extract(col, '$.key'); expand arrays with json_each(col).

RULES
- One statement. SELECT only.
- Range predicates:
    gte x -> COALESCE(value_max, value_num) >= x
    lte x -> COALESCE(value_min, value_num) <= x
    eq  x -> x BETWEEN COALESCE(value_min, value_num) AND COALESCE(value_max, value_num)
- value_kind 'composite' has all numerics NULL and matches no numeric predicate. When
  filtering numerically, also return a count of the composite rows excluded.
- Several spec filters at once need GROUP BY sku_code HAVING count(DISTINCT spec_id) = n.
- 'N/A' in a level column means the branch has no such level. Exclude it explicitly
  rather than treating it as a category.
- Never aggregate price where price_status = 'multiple_variants'. Exclude 'por' from
  numeric ranking and count those separately.
- Identify products by sku_code. Never return product_id or row_id.

Output only the SQL. No explanation, no fences.
```

---

## 8. Build order

| # | Step | Done when |
|---|---|---|
| 0 | Pre-flight queries (§0) | Max depth, fact volume, and `sqlite-vec` loadability all known |
| 1 | `build_sqlite.py` skeleton + `build_meta` + audits | Report lists factless SKUs, depth distribution, composite counts; exits 2 |
| 2 | `sku_fact` + indexes | 9,115 distinct `sku_code`, ~207k rows, depth assertion passes |
| 3 | `chunk` + FTS5 | 79,297 rows; lexical search returns sane hits |
| 4 | `backends/sqlite.py`: taxonomy, specs, search, get_sku | Identical results to the Postgres backend on 20 fixed queries |
| 5 | `resolve_product` on rapidfuzz | `CG24025W`, `CG 24 025 W`, `CG24025WNR` all resolve to one product |
| 6 | `get_price_detail`, `compare_skus`, `get_peer_group` | POR, `multiple_variants`, and context-mismatch cases correct |
| 7 | `search_documents` scalar-distance path | Filtered query < 50 ms; unfiltered call rejected with a clear error |
| 8 | Analytics subgraph on SQLite dialect | Golden SQL set passes, including the count-products case |
| 9 | `SqliteSaver` + thread-local pool | Five parallel sub-agents, no locking errors |
| 10 | Backend parity run | Same eval set through SQLite and Postgres; every difference explained |

Step 10 is the one not to skip. Two backends over one eval set is the cheapest available check that the migration did not quietly change answers — and once the Postgres path is deleted, it cannot be run.