"""Tool description strings — ship as written; they steer tool choice."""

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
