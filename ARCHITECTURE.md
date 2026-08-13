# C&S Product Agent V2 Architecture

## Runtime

The Python 3.11 CLI in `cs_agent.run` executes a LangGraph workflow over the
`cs_electric_v2.in_use.product_chunks` catalogue. PostgreSQL access uses psycopg for
materialized-view, vector, and analytical SQL. Synthetic fixtures provide the same
tool contracts to offline unit tests.

Model profiles and node routing live in `cs_agent/config/endpoints.yaml`. Anthropic and
vLLM use the OpenAI-compatible client; Ollama uses its native client. Intake has its
own node mapping, while all five specialists intentionally share the configurable
`agent` mapping. `CS_MODELS` can override one node or all nodes.

## Parent graph

```text
START → intake → planner
                  ├─ clarify → planner
                  └─ parallel specialist dispatch
                       ├─ discovery
                       ├─ spec_selection
                       ├─ solution_advisory
                       ├─ comparison
                       └─ compliance
                             ↓
                            gate
                       ├─ failed report → targeted retry once
                       └─ composer sufficiency
                            ├─ evidence gap → targeted revision
                            └─ compose_final → END
```

Only user-visible turns use parent `messages`. Every specialist is a private subgraph:

```text
prepare → agent ⇄ tools → record → report
```

This prevents concurrent tool traffic from interleaving and preserves Anthropic
tool-use/tool-result adjacency. Parallel state uses reducers: reports merge by agent;
evidence and completed tool-call counts add. Limits are loaded from
`cs_agent/config/limits.yaml` with `CS_*` overrides. The planner allocates each branch
before fan-out so concurrent branches never race on a shared budget.

The deterministic gate enforces role contracts, including actual representative SKUs
for discovery and SKU-bearing sources for specification findings. The composer first
returns a structured sufficiency decision. It may redispatch only the named specialist
with a concrete missing item; the final call composes from reports, not raw transcripts.
The numeric validator remains present but unwired.

## Multi-turn state

`PostgresSaver` persists state by `thread_id`. Intake rewrites pronouns and references
into a self-contained question from:

- previous turn summaries
- current focus SKUs and family
- resolved clarification parameters
- prior specialist reports

Clarification answers are persisted. Final composition updates focus SKUs, prior
reports, and a compact turn summary. Tool budgets are calculated per turn even though
the persisted completed-call counter is cumulative.

## Catalogue projection

`cs_agent/db/views.sql` builds eight materialized views:

- `mv_sku`: one row per `product_id`, including aliases, path, extraction, peer, and
  price metadata
- `mv_code_alias`: SKU, canonical, and alternate-code resolution
- `mv_fact`: long typed facts with range, composite, and source fields
- `mv_price`: provenance-aware observations and deterministic context mismatch flags
- `mv_source`: brochure markdown, product page, and pricelist references
- `mv_spec_registry`: family-level vocabulary, bounds, and composite counts
- `mv_facet`: decoded ordering-code axes by family
- `mv_chunk_index`: chunk presence and headings

Taxonomy is a 2–4 element JSON path. `_no_category` rows are pricelist sections and are
returned separately. `safe_num` prevents malformed numeric text from aborting a view.
Setup also creates `content_tsv` and migrates an empty embedding column to
`vector(768)`. It refuses to change dimensions if embeddings already exist.

Refresh order is:

```text
mv_sku
  → mv_code_alias, mv_fact, mv_price, mv_source
  → mv_spec_registry, mv_facet, mv_chunk_index
```

## Tools

All specialists receive `resolve_product`, `product_search`, and `get_sku`; additional
tools are bound by role. Structured tools cover path browsing, spec discovery,
provenance-aware price detail, peer groups, comparison, qualitative document search,
and delegated analytics.

Numeric product filters use range-aware predicates. Composite values cannot match a
number and are counted as `composite_excluded`, meaning unknown rather than rejected.
Price is never treated as an ordinary fact: `price_status`, source row context, and
`quotable` determine whether a figure may be stated.

`search_documents` requires a family or path prefilter. It checks for loaded vectors,
embeds the query with normalized `Alibaba-NLP/gte-base-en-v1.5` output, ranks with
pgvector cosine distance, and deduplicates identical content. With no vector result it
uses `content_tsv`, returning `mode: "lexical"`. Corpus embedding ingestion is external.

## Tests and operations

Activate `/home/rohan/Nyalazone/cs_electric_agent/venv` for every command.

```bash
make test       # fixtures only; no model downloads, PostgreSQL, or vector tests
make setup-db   # create v2 projection and full-text/vector schema
make refresh
make inspect
```

`tests/test_vector_retrieval.py` is excluded from the normal suite and guarded by
`CS_RUN_VECTOR_TESTS=1`. It is intended only after 768-dimensional corpus vectors are
loaded.
