"""Tool description strings — ship as written; they steer tool choice."""

LIST_CANONICAL_SPECS = (
    "List the specification IDs available for a category, with units, value kinds, "
    "how many SKUs carry each, and the observed minimum and maximum in the catalogue. "
    "ALWAYS call this before using product_search filters in a category you have not "
    "queried yet. Spec IDs are exact strings — guessing them returns nothing. Check "
    "observed_min/observed_max before filtering; an out-of-range threshold cannot match."
)

TAXONOMY_BROWSE = (
    "Browse the C&S catalogue structure: categories, families, and ordering-code axes "
    "(rating, poles, breaking capacity, release type, mounting), each with a SKU count. "
    "Use this first when you do not know what C&S sells and to distinguish an empty "
    "catalogue range from an incorrect filter."
)

PRODUCT_SEARCH = (
    "Find SKUs by specification filters, ordering-code facets, or code fragment. This "
    "is the PRIMARY tool for any number, rating, range, or superlative. Filters use "
    "exact spec_id values from list_canonical_specs. Range specs use their min/max "
    "bounds. Missing specifications mean not published, never zero."
)

GET_SKU = (
    "Everything known about one SKU: facts with units and value ranges, decoded "
    "ordering code, and optionally brochure text and sources. Use after search or "
    "browse identifies a sku_code. Completeness entries mean not published, not zero."
)

COMPARE_SKUS = (
    "Side-by-side specification table for 2–10 named SKUs. Use for straightforward "
    "comparison instead of analytics_query. Empty cells mean the spec is not published."
)

SEARCH_DOCUMENTS = (
    "Semantic search over brochure text. Use ONLY for qualitative questions: how a "
    "feature works, application suitability, or what a standard requires. Never use it "
    "to find, rank, or compare numeric ratings. Always pass category or family. Results "
    "shared across many SKUs are family-level text, not one SKU's specification."
)

ANALYTICS_QUERY = (
    "Run a free-form analytical query across many SKUs: aggregates, rankings, "
    "distributions, or pivots over more than ten products. Returns a table without "
    "interpretation. For 2–10 named SKUs use compare_skus."
)
