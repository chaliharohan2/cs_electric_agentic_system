# Tool payload slimming

What each catalogue tool stopped sending the specialist model, why, and what it
cost to measure. Every number here was measured against the built catalogue
(`artifacts/catalog-2026-08-20.sqlite`, 11,250 ordering codes) or against the two
captured specialist report calls in `logs/report_io/`.

The payloads themselves are beside this file:

```
before/    the nine calls as they were, indented           169,922 chars
after/     the same nine calls after the change            108,944 chars
```

`before/` was captured with the working tree stashed back to
`a3a6701`. Both directories hold the *same* nine calls, so the files diff
directly. Sizes quoted throughout are of the compact JSON actually put on the
wire — LangGraph's `ToolNode` serialises a dict result with `json.dumps`
defaults — not of the indented copies stored here.

## Why

Tool payloads are the specialist report's input, and the report is the slow
step. Two captured report calls:

| | `changeover` | `compare` |
|---|---|---|
| input | 97,661 chars (~24,415 tok) | **235,289 chars (~58,822 tok)** |
| usable window | 60,000 tok | 60,000 tok — **98% full** |
| dominated by | five `get_sku` = **63.5%** | three `product_search` = **91%** |

`usable = num_ctx − num_predict` = 80,000 − 20,000 (`context_guard.py:83`).
Exceeding it makes Ollama truncate the prompt head, which changes the cached
prefix and destroys the KV cache — measured once at 86s → 365s. `compare` had
roughly 1,200 tokens of headroom: one more tool call.

Decode runs at 34 tok/s against an effective 1,717 tok/s prefill, so a token
removed from a payload is worth far less than one removed from the report. But
these payloads are also what the model reads *while* deciding what to write, and
`compare` was one call from falling off the window entirely.

## The result

| call | before | after | saved | |
|---|---|---|---|---|
| `product_search.winmaster3` | 91,455 | 60,632 | 30,823 | 33.7% |
| `product_search.winmaster2` | 32,265 | 14,810 | 17,455 | 54.1% |
| `get_sku.changeover` | 11,788 | 6,396 | 5,392 | 45.7% |
| `get_peer_group.changeover` | 9,423 | 4,904 | 4,519 | 48.0% |
| `product_search.grouped` | 9,101 | 7,064 | 2,037 | 22.4% |
| `resolve_product.changeover` | 2,477 | 2,202 | 275 | 11.1% |
| `search_documents.winmaster3` | 5,839 | 5,593 | 246 | 4.2% |
| `list_canonical_specs.two_acbs` | 6,113 | 5,924 | 189 | 3.1% |
| `catalogue_map.winmaster` | 1,461 | 1,419 | 42 | 2.9% |
| **total** | **169,922** | **108,944** | **60,978** | **35.9%** |

Applying the two measured `product_search` ratios to the three payloads in the
captured `compare` report — a projection, not a measurement, because that run
has not been repeated — its input goes from **235,289 to ~156,600 chars**,
~58,822 to ~39,100 tokens: **98% of the usable window down to 65%.**

## Changes, tool by tool

### `product_search`

| field | change | why |
|---|---|---|
| `hits[].spec_label` | **cut** | On one measured call there were **7 distinct `(spec_id, spec_label)` pairs across 274 spec rows** — the seven ids the caller asked for by name. 11.2% of the payload restating seven definitions. `list_canonical_specs` publishes the labels; both tools also match a spec by its label. |
| `hits[].canonical_code` | **cut** | Identical to `sku_code` on **11,217 of 11,250** ordering codes (99.7%) and on 40/40 hits here. A search answers with the code you order by; `resolve_product` is where an alternate spelling gets sorted out. |
| `hits[].decoded` | **reshaped** | `{"acb_type": {"code": "MDO", "meaning": "Manual Draw Out Type"}}` → `{"acb_type": "Manual Draw Out Type"}`. The `code` half is a literal substring of the `sku_code` printed on the same row. A nested meaning carrying several facts survives whole (`breaking` → `{"ka": 80, "volts": 415}`); a single-key meaning restating its own axis is unwrapped (`poles` → `3`); an axis whose meaning is `"unknown"` is left out; a hit with nothing decoded carries no `decoded` key. **19.0% → ~8%.** |
| `hits[].url` | **hoisted to `scope`** | **One distinct value across all 40 hits.** The catalogue publishes 42 URLs for 11,250 SKUs. It *is* used — both URLs in the compare capture reached the answer — so it is stated once, not dropped. |
| `hits[].path` | **hoisted to `scope`** | One distinct value across 40 hits. |
| `hits[].family` | **hoisted to `scope`** | One distinct value across 40 hits — *when the search is scoped to one family*. Grouped by family it differs between rows and stays on the rows. |
| everything else | unchanged | `source_of_truth`, `value_display`, `spec_id`, `value_kind`, `value_min`/`value_max`, `value_num`, `unit`, `sku_code`, `price_quotable`, `price_status`, `description`, `price_inr`, `total_matched`, `composite_excluded`, `filters_applied`, `widening_hint`. |

The hoist is decided per call, not assumed: a field is moved only when every row
in the payload agrees on it, so a grouped search keeps its per-row `family`. A
field uniformly `null` is dropped rather than hoisted — an absent key already
means "not published", which is what the tool descriptions tell the model.

### `get_sku`

| field | change | why |
|---|---|---|
| `facts[].fact_sentence` | **cut** | The single largest line item in the audit at **31.0%** of the payload. A template: *"E-CSCS400DM4CO (New Changeover Switches, 400 A, 4-pole) has a ambient / cubicle service temperature of 40 °C."* Across 200,000 catalogue rows **87.9%** contain both `spec_label` and `value_display` verbatim, and the remaining 12% are template variants carrying nothing the neighbouring columns do not. Mean length 113 chars. **Not one of the 141 sentences in the changeover capture reached the report or the answer.** |
| `facts[].spec_label` | **cut** | 8.3%. |
| `facts[].is_canonical_spec` | **cut** | See below. |
| everything else | unchanged | including `url`, `canonical_code`, `decoded` (**not** flattened here — a single-SKU call has one decode, not forty), `value_min`/`value_max`, `value_kind`, `source_pdf`, `source_page`, `source_heading`, `path`, `headings`, `attributes`, `comparable_on`, `related_codes`, `also_published_as`, `alias_reason`, `extraction`, `fact_count`. |

### `get_peer_group`

- `peers[].decoded` **reshaped** — same flattening. It was **66.4%** of the payload.
- `peers[].family` **hoisted to `scope`** — a peer group sits inside one family by construction.
- Everything else unchanged, including the `truncated` note, which earns its 242 bytes by stopping the model re-issuing the call.

### `search_documents`

- `[].mode` **cut** — retrieval internals. Which index answered is not something the model should reason about. A `distance` is still present on exactly the vector path, so which scale `score` is on stays readable from the payload itself.
- `[].chunk_id` **cut** — a build-source row number with no citation value, and a number the model could quote at a customer.
- Everything else unchanged, including `distance`, `score`, `shared_by_sku_count`, `text`, `headings`, `brochure_md`.

### `resolve_product`

- `hits[].canonical_code` **cut** — the 99.7% rule again. `match_role` and `alias_note` are what actually explain a resolution, and both stay.
- Everything else unchanged, including `path_text`, `description`, `alias_reason`, `score`.

### `catalogue_map`

- `matched_on.path_text` **cut** — the caller's own free-text argument, visible in the tool call immediately above the result. Reading it back told the model nothing it had not just written. `matched_on` is omitted entirely when it would be empty.
- `matched_on.market_segment` **kept** — it is validated against a closed seven-value vocabulary, so seeing which value took effect is an answer rather than an echo.
- Everything else unchanged.

### `is_canonical_spec`, everywhere

Removed from every payload and every prompt: `get_sku` facts, the
`list_canonical_specs` spec rows (`spec_envelope.group_specs`), and the column
list in `prompts/analytics_write_sql.md`.

It splits the catalogue almost evenly — 123,800 rows true against 139,828 false
— so it is a real signal. It was read by nothing: neither captured report
contains it, no prompt mentioned it, and no consumer outside the catalogue
touched it.

**It survives in the built artifact**, because two things still use the column:
the `canonical_only` filter argument on `list_canonical_specs`, and the ordering
in `analytics/nodes.py:_registry_rows` that puts canonical specs first in the
vocabulary handed to the SQL writer. Both are internal; neither is sent to a
model. The `canonical_only` **argument** is therefore unchanged and still works.

### Not changed

`compare_skus`, `get_price_detail`, `analytics_query` and `taxonomy_browse` are
untouched. `compare_skus` is already the shape this whole exercise argues for —
a `rows[spec_id][sku_code]` matrix with the axes declared once, 523 chars for a
two-SKU comparison.

Deferred (tier 3, not done): `product_search` with `group_by` still embeds up to
20 full `sample_hits`; `decoded` still arrives unrequested on every search hit
rather than behind an `include` flag; `limit` is still whatever the model asks
for, up to 100.

## Code

New: **`cs_agent/backends/payload_shape.py`** — `flatten_decoded`, `hoist_scope`,
`merge_scope`. Both backends import it, so the fixtures backend returns the same
shapes the SQLite one does and the test suite exercises the real contract.

Changed:

| file | what |
|---|---|
| `backends/sqlite.py` | the cuts, the flattening, the two hoist calls |
| `backends/fixtures.py` | the same, mirrored |
| `backends/spec_envelope.py` | `group_specs` stops emitting `is_canonical_spec`; `compact_fact` docstring records why `spec_label` left `product_search` but not `list_canonical_specs` |
| `subgraphs/agents/report_modes.py` | `_search_hits` merges `scope` back under each row, so a derived report still finds family, path and URL after the hoist; the source-ref builder reads a hoisted `url` |
| `graph/nodes/record_evidence.py` | comment only — see below |
| `tools/descriptions.py` | `product_search` describes `scope` and says attached specs are keyed by `spec_id`; `search_documents` explains `distance` in place of `mode`; `get_sku`, `get_peer_group`, `resolve_product` updated |
| `prompts/agent_common.md` | one paragraph telling specialists where `scope` lives and that citing a family from it is right rather than a guess |
| `prompts/analytics_write_sql.md` | `is_canonical_spec` off the column list |

## Two consequences worth knowing

**The composer's evidence table now prints `text=null` for catalogue facts.**
`record_evidence._fact_record` sourced that column from `fact_sentence`. Nothing
is lost — the same row already prints `spec`, `value_num`, `value_min`,
`value_max`, `value_display`, `value_kind`, `unit` and `source` beside it, which
is everything the sentence restated — and the composer's own prompt gets shorter
by the same amount. The read was left in place so a payload that *does* carry a
sentence (an older trace replayed) still uses it.

**33 ordering codes have a `canonical_code` that differs from their `sku_code`.**
`product_search` and `resolve_product` no longer surface it for those. The
resolution path still reports the relationship through `match_role` and
`alias_note`, and `get_sku` still returns `canonical_code` in full.

## Tests

`tests/test_framework.py::PayloadShapeTests` — 19 tests pinning both halves of
every change: the field is gone, and the fact it carried still arrives. Four
existing tests were re-pinned to the new contract rather than deleted
(`test_matched_on_reports_only_the_filters_used`,
`test_document_fixture_is_lexical_and_v2_shaped`,
`test_product_search_family_list_and_string_prefix`,
`test_product_search_group_by_level_uses_path_scope`), plus three in
`test_sqlite.py` and `test_vector_retrieval.py` that asserted on `mode`.

Suite: **252 + 28 passing.**
