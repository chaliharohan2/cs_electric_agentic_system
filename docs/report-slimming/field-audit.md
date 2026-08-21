# What each specialist report carries, and what it costs

Companion to `docs/payload-slimming/`, which cut what the *tools* send **into**
the model. This one audits what the *specialists* send **out** of it.

## Method

Two costs, and they are not the same field list.

* **Decode** — what the model actually generates. Measured on the two captures
  in `logs/report_io/`, which hold a report call's exact input and output.
  This is the expensive one: ~34 tok/s.
* **Prefill** — what the composer reads. The whole `reports` dict goes to the
  composer twice, once for the sufficiency check and once for `compose_final`
  (`composer.py:86` and `composer.py:111`). Some of it the model never wrote:
  `sources` and the four document fields on every `SourceRef` are hidden from
  the schema and put back by `backfill_report`, so they are free to produce and
  are paid for twice on the way out.

Corpus: 82 distinct reports mined from `logs/**`, plus the four `logs/bench_final`
runs end to end, plus the two `logs/report_io` captures. No compliance report
exists in any trace, so its verdicts below are from the schema and the gate, not
from measurement.

## Where the weight is

Composer input for the four `bench_final` runs, against the answer produced:

| run | reports dict | answer | ratio |
|---|---|---|---|
| changeover | 25,158 | 1,282 | 19.6x |
| wintrip | 8,874 | 840 | 10.6x |
| residential | 11,426 | 1,946 | 5.9x |
| compare | 9,681 | 1,703 | 5.7x |

The worst of them, broken down:

| | chars | % |
|---|---|---|
| `candidates` | 12,928 | 55.2% |
| `findings` | 4,673 | 19.9% |
| `sources` | 3,443 | 14.7% |
| `gaps` | 918 | 3.9% |
| `caveats` | 634 | 2.7% |
| `summary` | 627 | 2.7% |
| everything else | 193 | 0.8% |

and the single largest leaf in it is **`candidates[].key_specs[].source.product_page_url`
at 5,023 chars — 21.4% of everything the composer reads.** 33 key_specs carry a
source ref; there are 14 distinct refs among them and 2 distinct URLs.

Across all four runs, **10.4% of the composer's input is a key whose value is
`null`** (5,347 of 51,477 chars). None of it is written by the model —
`model_dump()` emits every schema field, and `backfill_report` writes `null`
into a ref for a document the payload did not have.

---

## Shared fields — every agent

| field | who writes it | cost | verdict |
|---|---|---|---|
| `agent` | model | 25 chars | **cut from the write.** The subgraph knows which agent it is; `make_report_node` is built per agent. Set it in code. |
| `status` | model | 20 chars | **keep.** Three values, read by the gate and the composer. |
| `summary` | model | 2.7–7.6% | **keep.** Judgement, and the only field that survives into `digest_report` verbatim. |
| `findings[].statement` | model | **6.8–34.6%, the largest thing the model writes** | **reshape.** See below. |
| `findings[].kind` | model | 1.9–3.5% | **keep.** The gate's citation rule keys on it. |
| `findings[].source.sku_code` / `.family` | model | 1.7–5.3% | **keep.** This is the citation. |
| `findings[].source.source_of_truth` | model | 2.8–3.4% | **keep** — a price citation is built from it. |
| `findings[].source.{brochure_md, pricelist_pdf, pricelist_page, product_page_url}` | **code** | 6.5% of composer input on the changeover run | **reshape** — hoist to `sources`, see below. |
| `sources` | **code** | 14.7% | **reshape.** Keep the list; it is the right place for the document refs. It should be the *only* place. |
| `gaps` | model | 3.9–10.6% | **keep.** Feeds the sufficiency check directly. |
| `caveats` | model | 2.7–9.2% | **keep**, but cap. Uncapped today. |
| `tool_calls_used` | code | 20 chars | keep. |
| `raw_results` | code | up to 6,101 chars | **keep as is** — it is the whole point of `raw` mode, and already budget-capped. |

### The one cut that needs no model change

Every `SourceRef` nested inside a finding, a candidate's key_spec, a standards
claim or an advisory claim gets the four document fields backfilled onto it.
On the changeover run that is 33 copies of 2 URLs and 5 pricelist references.

Leave the document refs in `sources` only, keyed by `sku_code`, and let the
nested refs carry `sku_code` / `family` / `source_of_truth` alone. Combined with
`exclude_none=True` on the dump:

| | chars | |
|---|---|---|
| composer input today | 25,053 | |
| null-valued keys dropped | 22,398 | −11% |
| + document refs left only in `sources` | **13,279** | **−47%** |

**47% off the composer's prefill, and the model's output does not change at all.**

### `findings[].statement`

The largest single thing the model writes, and roughly half of it is not
judgement. From the changeover capture:

> `"CSCS400DM4CO: 400A, 4-pole, 415V, IP54, width 4 modules, pollution degree 3,
> utilisation category AC23A, short-circuit current with fuses (rated fused
> short-circuit level) 80 kA rms, listed MRP ₹60,910."`

That is a value list, and every value in it came out of a `get_sku` payload.
Six of the eight findings on that report are `kind: "specification"` and read
like this. The other two are the reason the specialist is worth running:

> `"Neither family publishes a physical dimensions (mm/W×H×D) spec for these
> SKUs; the only quantitative size proxy available in the catalogue is 'modules'
> (width in DIN modules), which is 4 for every candidate — no differentiation on
> footprint is possible from that alone."`

**Verdict: reshape.** A `specification` finding should be a citation
(`sku_code` + the `spec_id`s), expanded in code. A `catalogue` or `general`
finding stays prose.

---

## discovery — mean 6,409 chars

| field | populated | cost | verdict |
|---|---|---|---|
| `families[].name` | 183/183 | 2.5% | **keep** |
| `families[].path` | 183/183 | 7.0% | **keep** — `taxonomy_browse` and `product_search` take it directly |
| `families[].sku_count` | 183/183 | 1.2% | **keep** |
| `families[].url` | 180/183 | **9.4%** | **cut from the write, keep in `sources`.** Verbatim from `catalogue_map`; the answer cites it at most once. |
| `families[].description` | 177/183 | 5.4% | **keep**, but it is verbatim from `catalogue_map.groups[].description` — a candidate for citation rather than copying |
| `representative_skus` | **2/36** | ~0 | **keep.** Cheap, and the gate requires it or an explicit gap at detailed depth. |
| `follow_up_questions` | 33/36 | 4.5% | **keep.** Pure judgement, and the gate requires one at overview depth. Worth noting the derived-mode templates are already visible in the corpus: 12 reports ask *"Would you like ordering codes and ratings for any of these ranges?"* verbatim. |
| `uncategorised_note` | 3/36 | 0.6% | **keep** — rare, and says something no other field does |

`families` is the clearest case in the whole audit: 183 of 183 entries are a
verbatim `catalogue_map` row. `derive_report` already rebuilds it exactly
(`report_modes._families`), which is why `auto` runs discovery through `raw`.

## spec_selection — mean 15,261 chars, the heaviest agent

| field | populated | cost | verdict |
|---|---|---|---|
| `candidates[].sku_code` | 22/25 | 1.5% | **keep** |
| `candidates[].family` | | 2.5% | **keep** |
| `candidates[].why_it_fits` | | 10.3% | **keep.** Judgement, and the field the answer leans on hardest. |
| `candidates[].price_status` | | 1.2% | **keep** |
| `candidates[].key_specs[].spec_id` | | 8.1% | **keep as the citation** |
| `candidates[].key_specs[].value_display` | | 8.0% | **cut from the write, fill in code** |
| `candidates[].key_specs[].unit` | | 2.9% | **cut from the write, fill in code** |
| `candidates[].key_specs[].source.sku_code` | | 7.3% | **cut.** 466 of 469 key_specs across the corpus carry a `source.sku_code` identical to the candidate they hang under. The 3 exceptions are candidates with no `sku_code` of their own. |
| `candidates[].key_specs[].source.*` (documents) | code | **21.4% of composer input** | **cut, hoist to `sources`** |
| `filters_tried` | 24/25 | 1.7% | **keep.** The gate pairs it with `no_candidates_reason`. |
| `no_candidates_reason` | 2/25 | 0.3% | **keep** |

Two measurements on `key_specs`:

* **100% of its leaf values are verbatim in the tool payloads.** 95 of 95 values
  across the changeover report; of the 50 distinctive enough to test (≥4 chars),
  50 matched — including `₹60,910`, `80 kA rms`, and
  `IP 54 (using a suitable gasket along with the handle)`.
* **89% are already restated in the same report's own `findings` or `summary`**
  (419 of 469 across the corpus). On the changeover run, every fact `key_specs`
  contributed to the final answer was also in a finding; four facts the answer
  used — 415 V, pollution degree 3, AC23A, mechanical interlock — came **only**
  from a finding.

So `key_specs` today is a third statement of values the model already stated
twice, retyped from a payload the composer could re-read.

**How a cited spec is addressed.** `(sku_code, spec_id)` resolves a fact
unambiguously for 98.3% of the catalogue. It does not for the rest: 317
`(sku, spec_id)` pairs across 325 SKUs publish more than one distinct value —
`CSDBTPNDDPRE04` publishes `terminal_block_count` as both `4 Nos.` and
`12 Nos.`. Adding the source `fact_id` to the key leaves 1 of those 317
ambiguous. The tie is broken with `sku_fact.row_id`, which is unique on all
265,979 rows and needs no rebuild; it should ride on a payload row only when
that row's `(sku, spec_id)` is duplicated within the same payload. Details and
cost in `report-tool.md` §2.

## comparison — mean 10,676 chars

| field | populated | cost | verdict |
|---|---|---|---|
| `table.axes` | 18/18 | 2.0% | **keep** |
| `table.rows` | 18/18 | 11.2% | **depends on the question — see below** |
| `differentiators` | 12/18 | 10.3% | **keep.** Judgement; nothing else in the report says it. |
| `peer_group_match` | **1/18** | 25 chars | **keep**; too cheap to argue about |

`table.rows` splits in two and the split matters:

* **SKU-level comparison** — the rows are `compare_skus` output verbatim.
  `report_modes._table` already rebuilds them exactly.
* **Range-level comparison** — `compare_skus` cannot be called (it takes
  ordering codes), and the model synthesises the rows from `product_search`.
  From the `compare.report_io` capture, over 214 KB of search payloads:

  > `"rated_current_a": "630–2500 A for breaker SKUs (0.2–1A range seen only on
  > accessory/release-setting SKUs)"`

  Noticing that the sub-1 A values belong to accessory SKUs rather than breakers
  is not in any payload. **Do not mechanise this one.** It is also why
  `derived_core_is_empty` fires here and falls back to the model.

## compliance — no report in any trace

| field | verdict |
|---|---|
| `standards[]` | **cut `value_display` from the write, keep `sku_code` + `spec_id`.** Identical case to `key_specs`, and `_standards` already derives the whole list from evidence rows. |
| `certifications` | keep |
| `not_established` | keep |

## solution_advisory — 3 reports, mean 4,685 chars

`catalog_backed`, `engineering_guidance` and `recommended_slots` are all prose
judgement and none of them is derivable — this is the agent `NOT_DERIVABLE`
already exempts. **Keep everything.** Its only shared-field cost is the same
`SourceRef` backfill as everyone else.

---

## Summary of verdicts

**Cut from the write** (model stops generating; code fills or drops):
`agent`; `candidates[].key_specs[].value_display`, `.unit`,
`.source.sku_code`; `families[].url`; `standards[].value_display`.

**Reshape:** `findings[]` splits into cited specification claims and prose
claims; every nested `SourceRef` loses its document fields to `sources`;
`table.rows` mechanised for SKU-level comparisons only.

**Keep unchanged:** `status`, `summary`, `gaps`, `caveats`, `filters_tried`,
`no_candidates_reason`, `why_it_fits`, `differentiators`, `follow_up_questions`,
`representative_skus`, `uncategorised_note`, `peer_group_match`,
`certifications`, `not_established`, and all three advisory fields.

**Free, no model change:** `exclude_none=True` on the dump, and document refs
in `sources` only — together 47% off the composer's prefill.

## One prerequisite, whichever verdicts are taken

Every "fill it in code" verdict above needs a fact index to fill from, and the
one that exists does not cover enough. `record_evidence._extract` reads
`payload["specs"]` and `payload["rows"][].facts` but never descends into
`payload["hits"][]`, so a `product_search` with `return_specs` produces **zero**
evidence rows even when its hits carry fully-formed facts with `source_pdf` and
`source_page`. On the `auto__changeover` bench run this shows end to end: 17 of
the 33 cited `key_specs` resolve against the index and 16 do not.

It is worth fixing independently of any of this — the composer's evidence table
and `derive_report`'s findings read the same index and are equally blind to
anything retrieved by search.
