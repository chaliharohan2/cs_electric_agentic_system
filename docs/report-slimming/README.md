# Report slimming

What each specialist stopped writing, what fills it in instead, and what it
cost to measure.

* [`field-audit.md`](field-audit.md) — every field of every specialist report,
  with its measured cost and a keep / cut / reshape verdict.
* [`report-tool.md`](report-tool.md) — the design decision behind this: why a
  formatter function rather than a report tool, and why neither a tool nor a
  constrained decode saves a single token on its own.

This file records what was actually built.

## The shape of the change

The model writes what only it can write — the summary, why an entry fits, the
gaps, the caveats, and the findings that are judgement rather than retrieval —
and **names** everything else. A Python formatter turns those names back into
facts, reading the tool payloads the specialist already received.

```
before   "key_specs": [
           {"spec_id": "rated_current_a", "value_display": "400 A", "unit": "A",
            "source": {"sku_code": "CSCS400DM4CO", "brochure_md": null,
                       "pricelist_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
                       "pricelist_page": 42, "product_page_url": "https://…",
                       "source_of_truth": "code_grammar"}},
           … 24 more
         ]

after    "key_specs": ["rated_current_a", "poles", "modules",
                       "ip_level_after_mounting", "price_inr"]
```

The value, the unit and the source come back in code. The document reference
moves to the candidate, once, and to `sources`.

## Projected

On the captured `spec_selection` report in `logs/report_io/changeover.report_io.txt`,
re-expressed field by field under the new schema:

| field | model writes today | model writes now |
|---|---|---|
| `candidates` | 4,492 | 2,013 |
| `findings` | 2,571 | 1,759 |
| `summary` | 650 | 650 |
| `gaps` | 605 | 605 |
| `caveats` | 336 | 336 |
| `filters_tried` | 150 | 150 |
| `agent` + `status` + `tool_calls_used` + `no_candidates_reason` | 101 | 44 |
| **total** | **8,905** | **5,557** |

**−38%** projected. The live run below came in at −19%, because the model spent
most of the saving on the prose fields that carry no cap.

The schema the model is shown shrinks too, which is prefill rather than decode
and therefore worth about a second:

| | before | after |
|---|---|---|
| spec_selection | 7,045 | 4,692 |
| discovery | 5,733 | 4,485 |
| comparison | 4,896 | 3,646 |
| compliance | 5,492 | 3,642 |

## Changes

### Shared, every agent

| field | change |
|---|---|
| `agent` | **cut from the write.** Set by the subgraph, which is the only thing that knows which specialist is running. |
| `findings[]` | **reshaped.** A judgement finding is prose and cites nothing. A specification finding names its SKU and its `spec_id`s in `cite` and carries no statement; the formatter builds one. Six of eight findings on the captured report were the second kind. |
| nested `SourceRef` | **documents removed.** A reference identifies — `sku_code`, `family`, `source_of_truth` — and `sources` carries the pdf, the page and the product page once. Filling them in everywhere made `candidates[].key_specs[].source.product_page_url` **21.4%** of one composer prompt: 33 references, 14 distinct, two distinct URLs. |
| every field | **null-valued keys dropped.** 10.4% of four measured composer prompts (5,347 chars of 51,477), read twice a turn. |

### `spec_selection`

- `key_specs[]` is a **bare `spec_id`**, written as `["poles", "modules"]`. Asking for `{"spec_id": "poles"}` would spend 30 characters where 7 will do, once per row.
- `value_display`, `unit` and `source_of_truth` are **filled from the payload**. Across 469 measured key_specs every leaf value was verbatim in one the specialist already held.
- `source.sku_code` **cut** — identical to the candidate's own code on 466 of 469 rows.
- the reference is **hoisted to the candidate**, one per entry rather than one per spec.

`source_of_truth` stays per-spec rather than moving up with the rest of the
reference: a price fact reads `pricelist_table` beside a `brochure` fact on the
same SKU, and a price citation is built from it.

### `compliance`

`standards[].value_display` **cut from the write**; the claim names its
`sku_code` and `spec_id` and the formatter fills the value. A claim citing a
fact the specialist never retrieved is dropped and reported as a gap.

### Everything else

Unchanged. `discovery`, `comparison` and `solution_advisory` keep every field
they had, and so does every field of `spec_selection` and `compliance` not
listed above.

## Two properties this buys that the tokens do not

**A value in the report is a value a tool returned.** Nothing else can reach the
report: the model never writes a value, so it cannot write a wrong one. Before
this, a model that wrote `"value_display": "630 A"` for a 400 A SKU produced a
valid report and a wrong answer, and nothing in the pipeline could tell.

**A citation the specialist never retrieved is caught.** It is dropped from the
report and named in `gaps` — "Not retrieved, so not reported: CSCS400DM4CO/breaking_capacity_ka".
The gate then fails a report whose citations reached it unexpanded, so a
formatter that did not run cannot be mistaken for a catalogue that does not
publish the spec.

## Also fixed

`record_evidence._extract` never descended into `payload["hits"]`, so a
`product_search` with `return_specs` contributed **zero** evidence rows however
many facts it carried — a search returning three hits of three fully-formed
facts each, `source_pdf` and `source_page` included, produced nothing. Every
consumer of the index was blind at once: the composer's evidence table,
`derive_report`'s findings, and now the formatter. On the `auto__changeover`
bench run, 16 of the 33 facts the report cited could not be resolved against it,
all of them from SKUs reached by search rather than by `get_sku`.

## Measured live

Everything above is a projection off the captured report. This is the same
question run against `qwen3.8:27b` on the real server: a 16-message, 65,943-char
transcript built from real `catalogue_map`, `product_search` and five `get_sku`
payloads for the 400 A 4-pole changeover question, asked twice.

The old ask reproduced the captured report to within 1% (9,055 chars against
8,990), so the harness is exercising the real thing.

| field | old ask | new ask | |
|---|---|---|---|
| `candidates` | 5,218 | 2,770 | **−47%** |
| `findings` | 1,888 | 1,459 | −23% |
| `summary` | 759 | 728 | −4% |
| `gaps` | 510 | 726 | **+42%** |
| `caveats` | 404 | 722 | **+79%** |
| `filters_tried` | 120 | 738 | **+515%** |
| **total generated** | **9,055** | **7,299** | **−19%** |

**The mechanism works and the model spent the savings elsewhere.** `candidates`
came in at −47%, close to the −55% the projection expected. But the three
uncapped prose lists grew to absorb most of it: `filters_tried` alone went from
one line to six, and `why_it_fits` from a mean of 165 characters to 231.

Net −19% against a projected −38%. Capping `gaps`, `caveats` and `filters_tried`
the way `findings` is already capped is the obvious next move and is **not** done
here — those fields were on the keep-unchanged list.

Wall-clock is not quoted as a saving: the runs share a KV prefix and the first
one pays for it, so the later runs are flattered. Characters generated is the
honest number.

## Grammar-constrained decode: tried, measured, off

`structured()` can hand Ollama the same schema document the prompt was rendered
from, as `format`. It is **off by default**, because measuring it showed it made
the report worse:

| | generated | time | candidates naming a sku_code |
|---|---|---|---|
| `format` on | 5,483 | 102.5s | **0 of 5** |
| `format` off | 7,299 | 78.0s | 5 of 5 |

`sku_code` and `family` are `anyOf: [string, null]` and absent from `required`,
so omitting them is legal — and constrained sampling took that path on every
entry in the shortlist, producing a report the gate rejects outright. It also
applied `cite` to a judgement finding that the unconstrained run wrote as prose,
losing the sentence. And it decoded slower per token, not faster: roughly 13
tok/s against 23.

What it did settle is the open question from `report-tool.md` §1: **`format` and
bound tools do coexist.** Ollama accepted both together and parsed first time,
14.6s against 13.6s unconstrained on a small call. The mechanism works; what it
produced on this model was worse. `CS_STRUCTURED_FORMAT=1` turns it back on for
retesting against another model or server.

A related bug that testing caught: `format` is Ollama's, and `nodes.agent`
resolves to a hosted `ChatOpenAI` in other configurations of
`config/endpoints.yaml`. Binding it there would have put an unknown key in the
request body and failed the call, so it is now applied only to a `ChatOllama`.

## Code

| file | change |
|---|---|
| `contracts.py` | `Finding.cite` and a validator requiring a statement or a citation; `KeySpec` accepts a bare string and carries `source_of_truth` instead of a `SourceRef`; `Candidate.source` |
| `subgraphs/agents/report_format.py` | new — the fact index and the citation expansion |
| `subgraphs/agents/report_modes.py` | `HIDDEN_BY_DEF`, `SCALAR_DEFS`, `strip_empty`, and `backfill_report` putting documents only in `sources` |
| `subgraphs/agents/nodes.py` | `_asked_kwargs` feeds both the instruction and the grammar; the report node runs the formatter and sets `agent` |
| `llm/structured.py` | `asked_schema`, `_prune(scalars=…)`, `constrain_json`, `format_schema` |
| `graph/nodes/gate.py` | an unexpanded citation is a violation |
| `graph/nodes/record_evidence.py` | `_extract` descends into `hits[]` and `groups[].sample_hits` |
| `prompts/agent_common.md` | how to write each kind of finding |
| `prompts/agents/spec_selection.md`, `compliance.md` | key_specs and standards claims are citations |

## Tests

**273 + 28 passing.** 21 new, in `CitedReportTests` and `EvidenceFromSearchTests`:
the contract accepts a bare spec_id and rejects an empty finding; the schema
shown to the model has no `agent`, no `sources` and a string-typed `KeySpec`
while keeping every judgement field; the grammar and the instruction come from
one document; a cited spec is filled from `get_sku` and from a search hit alike;
an unretrieved citation becomes a gap; a prose finding is untouched; a unit the
value already carries is not said twice; the gate catches an unexpanded
citation; documents appear once; and `_extract` reads hits, grouped sample hits,
and a hit with no specs.

Two existing `BackfillTests` were re-pinned rather than deleted — they asserted
that a nested reference gains its documents, which is the behaviour this change
reverses.

## Testing instrumentation (temporary)

`CS_REPORT_IO=<dir>` dumps every report call to `<dir>/<agent>.report_io.txt`:
the full system prompt, every message the model saw, what it generated, and what
the formatter turned that into — with the decode time and rate on the header.

```
CS_REPORT_IO=logs/report_io python -m cs_agent.cli "…"
```

Silent when the variable is unset. This is scratch instrumentation for a testing
session and is meant to be removed before committing: delete
`cs_agent/subgraphs/agents/report_io.py` and the two lines in `nodes.py` that
reference it (the import, and the `report_io.capture(...)` call at the end of
`_generated`).
