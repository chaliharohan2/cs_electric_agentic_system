# On giving each specialist a report tool

Assessment of the proposal, revised after review. The three review points were
all substantive; two of them changed the recommendation, and one turned up
something that has to be checked before anything is built on it.

**Verdict: do it, as a shrunk schema plus a formatter function, not a tool.**
Measured at **−46% of the report decode** on a real captured report.

Two things changed in this revision. The saving comes *only* from asking the
model for fewer fields — neither a tool call nor a constrained decode reduces
generation, and §1 corrects an earlier claim of mine to the contrary. And the
citation key is `row_id`, not `fact_id`: §2 has the numbers, and the short
version is that `fact_id` is not unique and `row_id` already is.

## 1. The generation cost — `format` does not save tokens, and neither does a tool

Correcting myself: constraining the decode with `format` does **not** reduce
what the model generates. A grammar constrains *which* token may come next; it
does not skip any. The model still emits every brace, every key, every comma.
Ollama's sampler has no jump-ahead — it does not fill in a deterministic
continuation without a forward pass — so a schema-constrained report costs the
same number of decode steps as an unconstrained one of the same content.

The same applies to a tool call, which is why the first-round answer was right
and last round's concession was wrong. A tool call is the same JSON with a
wrapper around it: the model emits `{"name": "submit_report", "arguments": {…}}`
where structured output emits `{…}`. For identical content a tool call is
marginally *more* decode, not less.

**The only thing that reduces decode is the model writing fewer and shorter
fields.** That is the schema shrink, and it is the whole of the saving.

`format` is still worth having, but as robustness rather than speed: the report
generation today is unconstrained — `_build_ollama` never sets `format` — so
invalid JSON is caught only by `structured()`'s validate-and-retry, and each
retry is a *whole extra generation*. `_called()` records one comparison run
where the model answered with a tool call three times and cost the turn
**1,861s against the 465s** a first-parse run takes. A constrained decode cannot
do that. So: **not a prerequisite, and not a saving. A cheap insurance policy
against the retry path, to be picked up whenever convenient.**

## 2. The index — use `row_id`

The review point stands: derive nothing, use a key that is unique by
construction. `sku_fact.row_id` is exactly that, and it is already there.

| | |
|---|---|
| rows in `sku_fact` | 265,979 |
| distinct `row_id` | **265,979** |
| null | 0 |
| range | 1 … 265,979 |
| `row_id` vs SQLite `rowid` | the same — it is declared `INTEGER PRIMARY KEY`, so it is the rowid alias |

It needs no rebuild, no change to `mv_fact`, and no upstream fix. It is free to
select and free to index.

Compare what it replaces:

| candidate key | unique? | |
|---|---|---|
| `spec_id` | no | 317 `(sku, spec_id)` pairs resolve to more than one value, across 325 SKUs |
| `fact_id` | **no** | 266,121 facts, 263,403 distinct `(sku, fact_id)`. `TC1D3810-033` appears 11 times on one SKU with 10 distinct values. **579 SKUs** have colliding fact_ids — more than collide on spec_id |
| `(sku, spec_id, fact_id)` | nearly | 7 non-unique triples in 266,121 |
| **`row_id`** | **yes** | 265,979 of 265,979 |

`fact_id` also lives in the wrong place for the builder — it is in
`in_use.product_chunks.details->'facts'[]`, not in `in_use.mv_fact`, which is
what `build_sqlite.py` reads — and `sku_fact.fact_id` is presently populated as
a copy of `spec_id` (`build_sqlite.py:620`), so the column carries no
information. **Dropping `fact_id` from the plan removes a Postgres view change,
a builder change and a full rebuild.** Worth raising with whoever owns the
ingestion that the upstream ids collide, but nothing here needs to wait for it.

**Two cautions on shipping `row_id` in payloads.**

*It is an internal id.* This is the same objection that removed `product_id`
from spec rows in the last pass — *"an internal row id the model has no use for
and must not quote"*. The difference is that now something does use it. It has
to be named and described as an opaque handle, and the report formatter must
strip it, so it can never reach a customer.

*It is not free.* Six digits plus a key is ~16 chars a row against ~25 for a
full `fact_id`. On the 274-fact `product_search` that is roughly +4,400 chars,
+7%. The mitigation is the same as before: **emit it only when the payload holds
more than one row for that `(sku, spec_id)`** — 325 SKUs of 11,238, 2.9% — so a
normal call pays nothing and the ambiguous ones are addressed exactly.

**`_extract` still has to be fixed either way.** It reads `payload["specs"]` and
`payload["rows"][].facts` and never descends into `payload["hits"][]`, so a
`product_search` with `return_specs` contributes nothing to the fact index:

```
product_search(family="MCCB", return_specs=[...], limit=2)
  -> hits carrying fully-formed facts, source_pdf and source_page included
  -> _extract(...) == 0 evidence rows
```

End to end on the `auto__changeover` bench run, 17 of the 33 cited `key_specs`
resolve against the evidence index and 16 do not — every `E-CSCS400DM4CO` fact
missing, because it was reached by search rather than `get_sku`. A bug in its own
right: the composer's evidence table and `derive_report`'s findings read the
same index and are equally blind to search-retrieved facts.

## 3. Tool or formatter — taking the formatter, and why

Both shapes were offered; this picks the second. The deciding reason is
structural rather than a preference.

**`build.py` builds one tool list and hands it to both nodes.**

```python
tools = tools_for_agent(agent_name)
graph.add_node("agent",  make_agent_node(agent_name, tools))
graph.add_node("report", make_report_node(agent_name, tools))
```

A `submit_report` tool in that list is bound during retrieval, where it is a
standing invitation to end the loop early. Binding it only at report time is
worse: `structured()` documents that changing the bound set between the loop and
the report re-reads the whole transcript from cold, **808 tok/s against 91,611
tok/s on identical text**. There is no third position — the tool is either in the
loop's prefix or it breaks the prefix.

On top of that, `structured()` and `_called()` are built on the convention that
a tool call at report time is the error case, with a correction message and a
retry path that strips the tools. Making the report itself a tool call inverts
that convention and means rewriting all of it.

**The formatter has none of those problems and does the same job.** The model
answers a small schema; a Python function expands citations into facts, fills
the structural fields, and validates. That function *is* the gate: it runs in
the same place the values are filled, so a violation is caught with the payloads
in hand, and `structured()`'s existing validate-and-retry already handles
sending it back.

### How it actually works, and where the saving comes from

Three steps, and only the first one is decode.

**1. The model answers a smaller schema.** Where it writes this today:

```json
"key_specs": [
  {"spec_id": "rated_current_a", "value_display": "400 A", "unit": "A",
   "source": {"sku_code": "CSCS400DM4CO"}},
  {"spec_id": "poles", "value_display": "4", "unit": "count",
   "source": {"sku_code": "CSCS400DM4CO"}},
  ...
]
```

it writes this instead:

```json
"cite": ["rated_current_a", "poles", "modules", "ip_level_after_mounting", "price_inr"]
```

The saving is arithmetic: 25 objects of four keys each become one list of five
strings. Nothing clever is happening — the model is being asked for fewer and
shorter fields, and that is the entire mechanism.

**2. A Python function expands each citation.** It holds a fact index built from
this specialist's own tool payloads — `(sku_code, spec_id)` → the fact row, with
`row_id` breaking a tie where one exists — and turns `{"sku_code":
"CSCS400DM4CO", "cite": ["rated_current_a"]}` back into the full `KeySpec` with
`value_display`, `unit` and `source`. The values come from the payload, not from
the model, so they are right by construction.

**3. It fills the structural fields and validates.** `sources`, the document
refs, `agent`, `tool_calls_used`, and the gate's content rules. The output is an
ordinary `SpecSelectionReport`, so the gate, `digest_report` and the composer
see exactly what they see now.

Measured on the real changeover report, field by field:

| field | model writes today | model writes after |
|---|---|---|
| `candidates` | 4,492 | 1,634 |
| `findings` | 2,571 | 1,206 |
| `summary` | 650 | 650 |
| `gaps` | 605 | 605 |
| `caveats` | 336 | 336 |
| `filters_tried` | 150 | 150 |
| **total** | **8,990** | **4,879** |

**−46%**, on the conservative reading where every specification finding still
writes out its citation list. Dropping those findings entirely, on the grounds
that `key_specs` already carries them, gives −56%. Either way the prose fields
do not move, which is why the ceiling is where it is.

**If it does not reduce generation, the answer is that it does — but only step
1 does.** Steps 2 and 3 are free. If the schema were shrunk and the model still
wrote the same volume, the change would be worthless; the reason it will not is
that the model cannot write a field it has not been shown, which is the
mechanism `_asked_for` already relies on and measured at 61.8% of a detailed
report when `sources` and the four document fields were hidden.

**Keep a thin outer gate regardless**, for the one thing the formatter cannot
cover: `gate()` is where transcripts are released (the `{"__reset__": []}`
update), and without it every later checkpoint carries the full specialist
transcript. Its content rules move into the formatter; what stays is the
transcript reset and a check that a report arrived at all.

## 4. What will not shrink

Unchanged from the first pass, and worth keeping in view when judging the
result. These are judgement and no payload contains them: `summary`,
`why_it_fits`, `gaps`, `caveats`, `differentiators`, `follow_up_questions`,
`no_candidates_reason`, non-specification findings, and all three
`solution_advisory` fields.

Also range-level comparison tables. When the question is "compare the WiNmaster
ACB ranges", `compare_skus` cannot be called and the model builds the table from
`product_search`:

> `"rated_current_a": "630–2500 A for breaker SKUs (0.2–1A range seen only on accessory/release-setting SKUs)"`

Noticing that the sub-1 A values belong to accessory SKUs is not in any payload,
and `derived_core_is_empty` already falls back to the model here for that
reason. A citation-based table needs a prose escape hatch.

Those fields are roughly 45% of a current report. **The ceiling on decode is
55–60%, not 90%** — measured at 8,990 → 3,953 chars on the real changeover
report.

## 5. The argument that is better than the token saving

Nothing today checks that a `key_spec` the model wrote matches what the
catalogue published. The gate validates the schema; the schema does not know
what `rated_current_a` is for `CSCS400DM4CO`. A model that writes `630 A` there
produces a valid report and a wrong answer.

Under citation-expansion that is impossible by construction: a `(sku, spec_id)`
the specialist never retrieved is a formatter error, and every value in the
report is one the formatter read out of a payload. That is a correctness
property the gate cannot express, and a better reason to do this than the tokens.

## 6. Suggested order

1. **Free, no model change:** `exclude_none=True` on the report dump, and
   document refs in `sources` only rather than on every nested `SourceRef`.
   Measured at **47% off the composer's prefill** (25,053 → 13,279 chars),
   which is read twice per turn.
2. **Fix `_extract`** to descend into `hits[]`. Prerequisite for citation, and a
   bug on its own account.
3. **Shrink the report schema to citations and add the formatter**, moving the
   gate's content rules into it. **−46% off decode**, measured.
4. **`row_id` on ambiguous fact rows only**, if step 3 shows the ambiguity
   biting in practice. No rebuild, no Postgres change — 2.9% of SKUs are
   affected, so this is a correctness tail rather than a headline.
5. **`format` whenever convenient.** Not a saving and not a prerequisite; it
   removes the retry path that cost one run 1,861s.
