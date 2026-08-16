# SQLite catalogue schema and contents

This is the working description of the **runtime catalogue file** the agent
reads. Graph topology and tool contracts live in [`ARCHITECTURE.md`](ARCHITECTURE.md).
The build script is `scripts/build_sqlite.py`. Path depth is compiled in
`cs_agent/backends/path_levels.py`.

The file is **read-only** at runtime. Conversation checkpoints are a separate
SQLite file (`state/checkpoints.sqlite`) and are not described here.

---

## 1. Artifact

| Item | Value |
|---|---|
| Default path | `artifacts/catalog-latest.sqlite` (symlink) |
| Dated file | `artifacts/catalog-<YYYY-MM-DD>.sqlite` |
| Sidecar audit | `artifacts/build_report.json` |
| Typical size | ~1.9 GB (current build) |
| Artifact version | `1` (`build_meta.artifact_version`) |
| Git | Catalogue files are gitignored; only `artifacts/.gitkeep` is tracked |

Rebuild:

```bash
python -m cs_agent.db.refresh setup     # after changing views.sql (~17 min)
python -m cs_agent.db.refresh refresh   # after product_chunks reloads
python scripts/build_sqlite.py          # ~7 min
```

Changing a view definition needs `setup`, not `refresh` — `refresh` only
recomputes rows against the definitions already installed.

Source is live Postgres `cs_electric_v2`: materialized views `in_use.mv_*`
plus `in_use.product_chunks`. The views already resolve polymorphic fact
sources, pricelist regexes, and pricelist-header code matching. The build script
flattens those results into four application tables.

---

## 2. Design

**One structured table, one row per (SKU, fact).** There is no separate SKU
table. Identity, taxonomy, price summary, decode, and citations repeat on
every fact row for that SKU. A product with 28 facts occupies 28 identical
metadata copies plus one fact payload each.

**SKU-grain reads** collapse to one row per product:

```sql
WHERE row_id IN (SELECT min(row_id) FROM sku_fact GROUP BY sku_code)
```

`ix_sf_sku_row (sku_code, row_id)` makes that an index-friendly scan. Never
`count(*)` to count products — that counts fact rows (~28× too high). Use
`count(DISTINCT sku_code)`.

**Taxonomy is unnested, not nested JSON.** Live max path depth is **4**, so
the columns are `division`, `product_group`, `product_subgroup`,
`product_range`. Shallower branches pad unused levels with the literal
string `'N/A'` (the branch has no such level — not missing data). The leaf
of the path **is** the family, so the family name also appears in
`product_subgroup` (depth 3) or `product_range` (depth 4). Always filter
families on `family`, never on a level column.

**JSON is stored as TEXT.** SQLite has no native array/object type. Read with
`json_extract(col, '$.key')` and expand arrays with `json_each(col)`.

**Sentinel rows.** A SKU with zero facts would otherwise vanish. The builder
emits one row with `is_sentinel = 1` and all fact columns NULL so the SKU
stays visible to taxonomy and search. The current build has **zero**
sentinels (every SKU has at least one fact).

---

## 3. Tables

```text
sku_fact          structured catalogue (wide, denormalised)
taxonomy_level    published page metadata per catalogue node
chunk             brochure / pricelist text + embedding BLOB
chunk_fts         FTS5 virtual table over chunk.content
build_meta        key/value build diagnostics
sqlite_stat1      ANALYZE statistics (internal)
chunk_fts_*       FTS5 shadow tables — do not query
```

There is no foreign key from `chunk` to `sku_fact`. Join on `sku_code` (or
`product_id`) when needed. `search_documents` does not join: level columns
and `family` are duplicated onto `chunk`.

### 3.1 `sku_fact`

One row per `(sku_code, spec_id)`. `row_id` is the INTEGER PRIMARY KEY.

#### Identity

| Column | Type | Notes |
|---|---|---|
| `row_id` | INTEGER PK | Assigned on insert; used by the SKU-grain idiom |
| `is_sentinel` | INTEGER NOT NULL | `1` = no facts; fact columns NULL |
| `sku_code` | TEXT NOT NULL | Ordering code; the only product identifier tools may report |
| `canonical_code` | TEXT NOT NULL | Preferred spelling; equals `sku_code` when there is no alias |
| `product_id` | INTEGER | Postgres product id (build join key; do not show to users) |
| `family` | TEXT NOT NULL | Leaf name; filter here, not on a level column |
| `description` | TEXT | Published short description |
| `url` | TEXT | Product-page URL when known |

#### Taxonomy

| Column | Type | Notes |
|---|---|---|
| `division` | TEXT NOT NULL | Level 1; default `'N/A'` |
| `product_group` | TEXT NOT NULL | Level 2 |
| `product_subgroup` | TEXT NOT NULL | Level 3 |
| `product_range` | TEXT NOT NULL | Level 4 |
| `path_depth` | INTEGER NOT NULL | `0`, `2`, `3`, or `4` in the current build |
| `path_text` | TEXT NOT NULL | `"A > B > C"`; empty string when depth is 0 |
| `is_no_category` | INTEGER NOT NULL | `1` if division is `_no_category` (pricelist sections, not published categories) |

There is **no** `product_series` column. An earlier plan draft assumed depth 5;
pre-flight fixed depth at 4.

#### Commercial

| Column | Type | Notes |
|---|---|---|
| `price_status` | TEXT | One of seven statuses (see §5.1) |
| `price_quotable` | INTEGER | `1` when status is not `multiple_variants` **and** at least one observation carries a figure |
| `price_inr` | REAL | Best observation’s figure; may still be present when not quotable |
| `price_list` | TEXT | e.g. `LV`, `RETAIL` |
| `price_source_pdf` | TEXT | Pricelist filename for the chosen observation |
| `price_source_page` | INTEGER | Page of that observation |
| `price_effective_date` | TEXT | ISO date, e.g. `2026-06-01` |
| `price_context_ok` | INTEGER | `1` if any observation’s header text happens to name this SKU. Informational only — it does **not** gate quoting |
| `price_sibling_code` | TEXT | Set when the pricelist table header names a **different** ordering code. The figure may have been bound from that sibling; quote it only with the caveat |
| `price_observations` | TEXT JSON | Full observation array (see §4) |

Prices are MRP inclusive of GST. `price_inr` is a convenience column; quoting
rules go through `price_status` + `price_quotable`, and `price_sibling_code`
adds a mandatory disclosure when present.

**Why quotability ignores the header.** `price_observations[].context` is the
pricelist *table* header (`<first cell> | [HSN Code: …] | <section title>`), not
the SKU’s own row. Only 7 of 10,477 observations mention their own code, so the
former rule — quote only when the header names you — left **one** SKU in 9,115
quotable and the agent could never state a price. The header still earns its
keep as a defect signal: when its first cell is another product’s ordering code,
that is the multi-column price-binding defect (plan v2 §9), recorded as
`price_sibling_code` and disclosed rather than suppressed.

#### Relationships and decode

| Column | Type | Notes |
|---|---|---|
| `peer_group` | TEXT | Like-for-like comparison set (often the family name) |
| `comparable_on` | TEXT JSON | Spec ids (or `price_inr`) that peers share |
| `related_codes` | TEXT JSON | Nearby ordering codes |
| `also_published_as` | TEXT JSON | Alternate printed codes |
| `alias_reason` | TEXT | Why an alias exists (e.g. pricelist `NR` suffix) |
| `decoded` | TEXT JSON | Ordering-code axes: `{axis: {code, meaning, value?}}` |
| `attributes` | TEXT JSON | Extra product attributes when present |
| `market_segments` | TEXT JSON | Array of segment names |
| `market_segments_text` | TEXT | Same list joined with `\|` for `LIKE` |

#### Provenance and coverage

| Column | Type | Notes |
|---|---|---|
| `brochure_md` | TEXT | Brochure markdown filename, no page (by design) |
| `product_page_url` | TEXT | First `product_page` source |
| `pricelist_refs` | TEXT JSON | `[{pdf, page}, …]` |
| `sources` | TEXT JSON | Raw citation strings |
| `headings` | TEXT JSON | Brochure headings rolled up at SKU grain (often empty) |
| `spec_ids` | TEXT JSON | Spec ids present on this SKU |
| `chunk_types` | TEXT JSON | Which `chunk.chunk_type` values exist; used by `has_chunk_type` without joining `chunk` |
| `extraction_missing` | TEXT JSON | Specs the pipeline expected but did not find — report as “not published by C&S”, never as zero |
| `extraction_confidence` | TEXT | How much of the source was readable |
| `fact_count` | INTEGER NOT NULL | Number of fact rows for this SKU (`0` on sentinels) |
| `derived` | TEXT JSON | Build-time derived object when present |

#### The fact (NULL on sentinel rows)

| Column | Type | Notes |
|---|---|---|
| `fact_id` | TEXT | Same as `spec_id` in the current builder |
| `spec_id` | TEXT | Canonical snake_case id, e.g. `rated_current_a` |
| `spec_label` | TEXT | Human label |
| `unit` | TEXT | `A`, `V`, `kA`, `°C`, `INR`, … |
| `is_canonical_spec` | INTEGER | `1` if this spec is in the family’s canonical vocabulary |
| `value_num` | REAL | Scalar numeric; NULL for range / text / set / composite |
| `value_min` | REAL | Range lower bound |
| `value_max` | REAL | Range upper bound |
| `value_display` | TEXT | Printed text as published |
| `value_kind` | TEXT | `scalar` \| `range` \| `set` \| `text` \| `composite` |
| `source_of_truth` | TEXT | `pricelist_table` \| `brochure` \| `catalogue` \| `code_grammar` |
| `fact_source_pdf` | TEXT | Pricelist PDF when the fact came from a table |
| `fact_source_page` | INTEGER | Page of that table |
| `fact_source_heading` | TEXT | Brochure heading when applicable |
| `fact_sentence` | TEXT | Source sentence the fact was extracted from |

**Numeric filter semantics** (also in `prompts/analytics_write_sql.md`):

| op | Predicate |
|---|---|
| `gte x` | `COALESCE(value_max, value_num) >= x` |
| `lte x` | `COALESCE(value_min, value_num) <= x` |
| `eq x` | `x BETWEEN COALESCE(value_min, value_num) AND COALESCE(value_max, value_num)` |

`value_kind = 'composite'` has all numerics NULL. It never matches a numeric
predicate. Count those rows as *unknown*, not as ruled out.

#### Indexes

| Index | Columns |
|---|---|
| `ix_sf_sku_row` | `(sku_code, row_id)` |
| `ix_sf_spec_value` | `(spec_id, value_num)` |
| `ix_sf_family_spec` | `(family, spec_id)` |
| `ix_sf_family` | `(family)` |
| `ix_sf_levels` | `(division, product_group, product_subgroup)` |
| `ix_sf_value_kind` | `(value_kind)` |
| `ix_sf_price` | `(price_status)` |
| `ix_sf_canonical` | `(canonical_code)` |

### 3.2 `taxonomy_level`

The catalogue’s own published page metadata for each node of the hierarchy —
73 rows in the current build, one per distinct path prefix.

| Column | Type | Notes |
|---|---|---|
| `path_text` | TEXT PK | `"A > B > C"` — the node’s full path prefix, the browse lookup key |
| `name` | TEXT NOT NULL | The node’s own name (the last path element) |
| `level` | INTEGER NOT NULL | 1-based depth |
| `url` | TEXT | Published category / product page URL |
| `description` | TEXT | The node’s own `description`, falling back to the parent’s `contents[].note` about it |
| `is_leaf` | INTEGER | `1` when the published page marks it a leaf |
| `page_type` | TEXT | e.g. `category.md`, `product.md` |

Keyed on the path rather than the name because names are not guaranteed unique
across branches. `taxonomy_browse` joins it to fill each child’s `description`
and `url`, and returns the standing node’s own metadata under `node`.

A node’s own `description` is usually null while its parent’s one-line note
about it is not, so the build merges the two: 64 of 73 nodes end up described,
all 73 carry a URL.

### 3.3 `chunk`

One row per brochure/pricelist chunk that has an active `product_id` and
`sku_code`. Grain in practice is one row per `(product_id, chunk_type)`.

| Column | Type | Notes |
|---|---|---|
| `chunk_id` | INTEGER PK | Postgres `product_chunks.id` |
| `product_id` | INTEGER | Same as `sku_fact.product_id` |
| `sku_code` | TEXT NOT NULL | |
| `family` | TEXT NOT NULL | |
| `division` … `product_range` | TEXT NOT NULL | Same unnesting / `'N/A'` padding as `sku_fact` |
| `path_text` | TEXT NOT NULL | |
| `chunk_type` | TEXT NOT NULL | See §5.3 |
| `headings` | TEXT JSON | Array of heading strings |
| `content` | TEXT NOT NULL | Chunk body |
| `content_hash` | TEXT NOT NULL | MD5 of UTF-8 `content`; query-time dedup key |
| `content_len` | INTEGER NOT NULL | Character length |
| `brochure_md` | TEXT | SKU’s brochure filename (from `mv_source`) |
| `embedding` | BLOB | Little-endian `float32[768]` (3072 bytes), or NULL |

`search_documents` **requires** a `family`, `path`, or `sku_code` filter.
Unfiltered vector search is rejected in code.

Vector path: embed the query with `Alibaba-NLP/gte-base-en-v1.5` (normalized
768-d), rank survivors with `vec_distance_cosine(embedding, :qvec)`, dedupe
on `content_hash`, return `mode: "vector"`.

Lexical path: FTS5 over `chunk_fts`, then apply structured filters in Python,
return `mode: "lexical"`. Used when embeddings are absent, sqlite-vec cannot
load, or the vector query returns nothing.

#### Indexes

| Index | Columns |
|---|---|
| `ix_ch_family_type` | `(family, chunk_type)` |
| `ix_ch_sku` | `(sku_code)` |
| `ix_ch_type` | `(chunk_type)` |
| `ix_ch_hash` | `(content_hash)` |
| `ix_ch_levels` | `(division, product_group, product_subgroup)` |

### 3.4 `chunk_fts`

```sql
CREATE VIRTUAL TABLE chunk_fts USING fts5(
  content, content='chunk', content_rowid='chunk_id',
  tokenize='porter unicode61'
);
```

External-content FTS5: the text lives in `chunk.content`; `chunk_fts.rowid`
equals `chunk.chunk_id`. Rebuilt at the end of each catalogue build
(`INSERT INTO chunk_fts(chunk_fts) VALUES ('rebuild')`).

### 3.5 `build_meta`

Key/value TEXT pairs written at the end of the build. Also stored as a single
`full_json` blob.

| Key | Meaning |
|---|---|
| `source_database` | Host/db, credentials stripped |
| `built_at` | UTC ISO timestamp |
| `artifact_version` | Integer schema generation (`1`) |
| `compiled_path_depth` | `4` |
| `level_columns` | JSON array of the four level names |
| `max_observed_path_depth` | Pre-flight max from Postgres |
| `mv_counts` | `{mv_sku, mv_fact, product_chunks_active}` |
| `sku_fact_rows` / `distinct_skus` / `chunk_rows` | Row counts |
| `taxonomy_level_rows` | Nodes in `taxonomy_level` |
| `taxonomy_levels_with_url` / `taxonomy_levels_with_description` | Coverage of published page metadata |
| `taxonomy_descriptions_from_parent` | Descriptions filled from the parent’s `contents[].note` |
| `embedding_model` | Profile name, e.g. `gte_base_en_v1_5` |
| `embedding_dimension` | `768` |
| `embeddings_loaded` | True if any chunk has a non-NULL embedding |
| `null_embeddings` | Chunks with no vector |
| `factless_sku_count` | Sentinel count |
| `no_category_count` | SKUs under `_no_category` |
| `alias_collision_count` | One printed code mapping to two products |
| `quotable_sku_count` | SKUs whose price may be stated |
| `price_sibling_code_count` | SKUs whose pricelist table header names another code |
| `composite_count` | Fact rows with `value_kind = 'composite'` |

---

## 4. JSON column shapes

Examples from the current build (illustrative, not exhaustive).

**`decoded`** — ordering-code axes:

```json
{
  "door": {"code": "DD", "meaning": "double door"},
  "ways": {"code": "04", "value": 4, "meaning": 4},
  "config": {"code": "7SEG", "meaning": "7-segment TPN DB"}
}
```

**`price_observations`** — every pricelist hit for the SKU:

```json
[{
  "price": 17550.0,
  "price_list": "LV",
  "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
  "source_page": 136,
  "effective_date": "2026-06-01",
  "observation_status": "listed",
  "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
  "price_column": "MRP (`)",
  "context_names_own_code": false,
  "context_sibling_code": "CSDBPHSCDD12"
}]
```

`context` is the pricelist **table header**, not this SKU’s row, so
`context_names_own_code` is false for almost every observation and means very
little on its own. `context_sibling_code` is the load-bearing one: it is set
when that header’s first cell is another product’s ordering code, which marks
the multi-column binding defect. Quote the figure, and say where it came from.

**`pricelist_refs`:** `[{"pdf": "…pdf", "page": 136}, …]`

**`comparable_on` / `related_codes` / `also_published_as` / `market_segments` /
`spec_ids` / `chunk_types` / `extraction_missing`:** JSON arrays of strings.

**`chunk.headings`:** `["Construction and finish"]`

---

## 5. Controlled vocabularies

### 5.1 `price_status` (seven values)

| Status | Meaning | Quote a number? |
|---|---|---|
| `listed` | Published 2026 MRP | Yes when `price_quotable = 1`; add the caveat if `price_sibling_code` is set |
| `por` | Price on request | No |
| `multiple_variants` | One pricelist row covers several variants at different prices | **Never** |
| `brochure_price_only` | Figure from a brochure; may predate the current list | Yes, flagged as possibly stale |
| `not_listed` | Known to the catalogue, no current list price | No |
| `not_in_pricelist` | Absent from the current pricelist extract | No |
| `not_offered` | Explicitly not offered | No |

### 5.2 `value_kind`

| Kind | Numerics | Example `value_display` |
|---|---|---|
| `scalar` | `value_num` set | `25` |
| `range` | `value_min` / `value_max` | `-25 °C to +70 °C` |
| `set` | usually none | discrete published options |
| `text` | none | prose specification |
| `composite` | all NULL | `500A for 25A & 2200A for 125A` |

### 5.3 `source_of_truth`

| Value | Cite as |
|---|---|
| `pricelist_table` | (C&S pricelist) + PDF page when present |
| `brochure` | brochure markdown filename, no page |
| `catalogue` | catalogue / product page |
| `code_grammar` | derived from ordering code |

### 5.4 `chunk_type`

Nineteen values. Typical use:

| `chunk_type` | Use |
|---|---|
| `standards` | Conformity, certification, tests |
| `application` | Use cases |
| `installation` | Mounting and wiring |
| `features` | Construction benefits |
| `technical` / `technical_data` / `ratings` | Engineering detail (prose, not numeric lookup) |
| `specs` / `price` / `identity` / `ordering` | Structured-adjacent text |
| `accessories`, `construction`, `dimensions`, `environment`, `product_range`, `variants`, `losses`, `commercial` | As named |

Do not use document search to find or compare ampere/voltage ratings.

---

## 6. Taxonomy examples

| Depth | `path_text` | Level columns | `family` |
|---|---|---|---|
| 0 | *(empty)* | all `'N/A'` | e.g. `Motor Starter - Selection Chart` |
| 2 | `Final Distribution Products > Distribution Boards` | subgroup/range `'N/A'` | `Distribution Boards` (= `product_group`) |
| 3 | `Final Distribution Products > MCB & Isolators > WiNtrip MCB & Isolator` | range `'N/A'` | `WiNtrip MCB & Isolator` (= `product_subgroup`) |
| 4 | `Low Voltage Products and Solutions > Circuit Breakers > Air Circuit Breakers > ACB – AH-AHA` | all filled | `ACB – AH-AHA` (= `product_range`) |

Current divisions (SKU grain):

| Division | SKUs |
|---|---|
| Low Voltage Products and Solutions | 6600 |
| Final Distribution Products | 1912 |
| `'N/A'` (empty path) | 388 |
| Protection & Measurement Devices | 125 |
| LV Bustrunking | 90 |

`is_no_category` is **0** in the current build. Empty-path SKUs are not the
same as `_no_category`; they simply have no published taxonomy path.

---

## 7. How tools read the file

| Tool | Tables | Notes |
|---|---|---|
| `resolve_product` | `sku_fact` (+ FTS on `chunk` for text fallback) | Exact normalised code, then rapidfuzz `WRatio`, then description/family |
| `taxonomy_browse` | `sku_fact` SKU-grain + `taxonomy_level` | Walks level columns one step at a time; joins published description/URL per node, and rolls up decoded facet axes over the whole branch at any depth |
| `list_canonical_specs` | `sku_fact` | Aggregates `spec_id` / units / kinds per family |
| `product_search` | `sku_fact` SKU-grain, then fact rows | Path, family, facets, segment, price status, `chunk_types` JSON, spec predicates |
| `get_sku` | `sku_fact` + optional `chunk` | Full facts, decode, sources, price, peers |
| `get_price_detail` | `sku_fact` SKU-grain | Surfaces `price_observations`, `quotable`, and a `caveat` when `price_sibling_code` is set |
| `get_peer_group` | `sku_fact` | `peer_group` + `comparable_on` + `decoded` |
| `compare_skus` | `sku_fact` | Pivot on shared axes |
| `search_documents` | `chunk` / `chunk_fts` | Filtered vector or lexical |
| `analytics_query` | `sku_fact` / `chunk` | Read-only SELECT, SQLite dialect |

Runtime connections: one read-only URI connection per thread
(`file:…?mode=ro`), sqlite-vec loaded at open, pragmas from
`cs_agent/config/limits.yaml` (`query_only`, `mmap_size`, `cache_size`,
`temp_store`).

---

## 8. Current build snapshot

Taken from `artifacts/catalog-2026-08-16.sqlite` (`built_at`
`2026-08-16T12:25:52Z`, source `localhost:5432/cs_electric_v2`). Refresh this
section after each rebuild (or copy counts from `build_meta` /
`build_report.json`).

| Measure | Value |
|---|---|
| Distinct SKUs | 9,115 |
| `sku_fact` rows | 256,473 |
| Facts per SKU | min 1 · mean 28.1 · max 95 |
| Distinct `spec_id` | 1,079 |
| Distinct families | 66 |
| Chunks | 79,297 |
| Embeddings | 79,297 × 768-d; 0 NULL |
| Distinct `content_hash` | 79,297 (no duplicate bodies) |
| `taxonomy_level` nodes | 73 (73 with URL · 64 with a description) |
| Sentinel / factless SKUs | 0 |
| `_no_category` SKUs | 0 |
| Alias collisions | 0 |
| Composite facts | 14,419 |
| Quotable prices | 3,406 SKUs |
| Pricelist header names another code | 645 SKUs (412 of them quotable) |
| File size | ~1.9 GB |

**Path depth (SKU grain):** 388 depth 0 · 1,510 depth 2 · 6,025 depth 3 ·
1,192 depth 4.

**`value_kind` (fact rows):** 152,241 text · 58,939 scalar · 19,333 set ·
14,419 composite · 11,541 range.

**`source_of_truth`:** 122,272 pricelist_table · 119,790 brochure · 8,282
catalogue · 6,129 code_grammar.

**`price_status` (SKU grain):** 3,384 listed · 2,209 multiple_variants ·
1,362 not_listed · 1,129 por · 1,007 not_in_pricelist · 22 brochure_price_only
· 2 not_offered.

`price_quotable = 1` for **3,406** SKUs — every `listed` one plus the 22
`brochure_price_only`. Of those, **412** also carry a `price_sibling_code` and
must be quoted with the disclosure. `price_inr` is filled on some unquotable
SKUs too (notably `multiple_variants`); the presence of a figure is never on its
own a licence to quote it.

**`chunk_type` counts:** price 9,115 · specs 9,115 · identity 8,748 ·
ordering 7,174 · features 5,323 · accessories 5,063 · product_range 4,552 ·
environment 3,763 · ratings 3,457 · application 3,373 · technical 3,357 ·
technical_data 3,183 · dimensions 3,014 · construction 2,597 · installation
2,177 · standards 2,065 · variants 2,006 · losses 664 · commercial 551.

**Largest families (SKU count):** robusTa Contactors & Overload Relays 1,205 ·
exceeD Contactors 786 · Control & Signalling Devices 730 · Anmol Motor
Starter 723 · Distribution Boards 622 · Industrial Motor Starters 497 ·
MCCB – Winbreak1 431 · WiNtrip2 MCB & Isolator 408.

Common market segments: Industries, Infrastructure, OEM, Residential,
Commercial, Distribution & Transmission, Agriculture.

Common units: A, V, Hz, INR, %, mm, °C, count, kV, kA, operations.

### 8.1 All families (SKU grain)

| SKUs | Family |
|---:|---|
| 1205 | robusTa Contactors & Overload Relays |
| 786 | exceeD Contactors |
| 730 | Control & Signalling Devices |
| 723 | Anmol Motor Starter |
| 622 | Distribution Boards |
| 497 | Industrial Motor Starters |
| 431 | MCCB – Winbreak1 |
| 408 | WiNtrip2 MCB & Isolator |
| 316 | ACB – AH-AHA |
| 284 | Switch Disconnectors |
| 259 | Mini Contactor |
| 221 | Definite Purpose Contactors 1, 2, 3 & 4 Poles |
| 207 | Switch Disconnector Fuse |
| 172 | WiNtrip MCB & Isolator |
| 157 | DIVINO Switches |
| 157 | ACB – WiNmaster 3 |
| 144 | Primo Plus Switches |
| 126 | Primo Switches |
| 101 | ACB – WiNmaster 2 |
| 100 | Bridgg Modular Switches |
| 92 | HRC Fuse |
| 83 | Power Quality Device |
| 79 | Elusio Switches |
| 69 | RCBO |
| 63 | 2 & 4 Pole Contactors |
| 62 | Industrial Plugs and Sockets |
| 58 | Motor Protection Circuit Breakers |
| 57 | D Range Contactors |
| 50 | MCCB – Winbreak |
| 50 | MCCB – Winbreak2 |
| 50 | Motor Starter - Selection Chart |
| 50 | New Changeover Switches |
| 46 | WiNtrip2 DC MCB |
| 46 | mPRO-200 |
| 43 | Power Capacitor |
| 41 | robusTa2 Contactors |
| 40 | Lighting Trunking (LB) – LV |
| 40 | On-Load By Pass Switches |
| 37 | Changeover Switch (with & without fuse) |
| 35 | Sandwich Bustrunking (SB) – LV |
| 34 | Automatic Transfer Switch |
| 33 | Accessories |
| 30 | Capacitor Duty Contactor |
| 30 | Meter |
| 24 | WiNtrip ‘S’ Modular MCB |
| 22 | COMBI Weather Proof Enclosures |
| 21 | Rewirable |
| 18 | Anmol Smart Mobile Pump Controller |
| 17 | CD 2.0 |
| 17 | mPRO-100 |
| 16 | ELR 1.0 (7 segment display) |
| 15 | ACCL |
| 15 | Compact Air Bustrunking (CB)-LV |
| 14 | Alarm Annunciator |
| 14 | CSPTD Series SPD’s |
| 11 | mPRO-90 |
| 10 | Relay Range & Contactor Ratings Used in Motor Starters |
| 7 | DC Fuse |
| 6 | IRP-V3 |
| 6 | Residual Current Circuit Breaker |
| 6 | WiNtrip – MCB Changeover Switch |
| 4 | CSPF-100 |
| 3 | CSPF-200 |
| 2 | EGC-250 |
| 2 | MRN2(Mains De-coupling Device) |
| 1 | ELR 3.0 |

---

## 9. Build audits

Written to `artifacts/build_report.json` and summarised in `build_meta`.

| Audit | Policy |
|---|---|
| Path depth exceeds compiled column count | Hard fail |
| `sku_code` not unique per `product_id` | Hard fail |
| SKUs with zero facts | Warn, emit sentinel, exit 0 |
| Alias collisions | Warn + list |
| `value_kind = 'composite'` | Warn + count per family |
| Quotable prices | Info + count |
| Pricelist header naming another code | Warn + list `{sku_code, sibling_code, price_status}` |
| SKUs under `_no_category` | Warn + count |
| Chunks with NULL embedding | Warn; lexical-only until loaded |

---

## 10. What is not in this file

- LangGraph checkpoints (`state/checkpoints.sqlite`)
- Raw Postgres `product_chunks` JSON (already flattened)
- Helper views (`mv_sku`, `mv_fact`, …) — those exist only on Postgres as the
  **build source**
- A `vec0` virtual table — embeddings are BLOBs; distance is a scalar function
  over a pre-filtered set
