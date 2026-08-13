"""Tool description strings — ship as written; they steer tool choice."""

NAME_MATCHING = (
    "Names are matched loosely: case, spacing, hyphens versus dashes, and straight "
    "versus curly quotes are all ignored, and the words you give may appear in any "
    "order, so 'winmaster 2', 'ACB - WiNmaster 2' and 'WiNmaster2' all reach the "
    "'ACB – WiNmaster 2' catalogue entries. Give the words you know rather than "
    "guessing punctuation."
)

LIST_CANONICAL_SPECS = (
    "List the specification IDs available for a category, with units, value kinds, "
    "how many SKUs carry each, and the observed minimum and maximum in the catalogue. "
    "ALWAYS call this before using product_search filters in a category you have not "
    "queried yet. " + NAME_MATCHING + " Check observed_min/observed_max before "
    "filtering; an out-of-range threshold cannot match."
)

TAXONOMY_BROWSE = (
    "Browse the C&S catalogue structure: categories, families, and ordering-code axes "
    "(rating, poles, breaking capacity, release type, mounting), each with a SKU count. "
    "Pass nothing for every category, a category for its families, or a family on its "
    "own to get that family's axes without knowing its category. " + NAME_MATCHING +
    " Use this first when you do not know what C&S sells and to distinguish an empty "
    "catalogue range from an incorrect filter."
)

PRODUCT_SEARCH = (
    "Find SKUs by specification filters, ordering-code facets, or name and code "
    "fragments. This is the PRIMARY tool for any number, rating, range, or "
    "superlative, and the way to turn a product-line name into ordering codes. "
    + NAME_MATCHING + " Spec IDs also match their labels, so 'breaking capacity' "
    "finds breaking_capacity_ka. Range specs use their min/max bounds. Missing "
    "specifications mean not published, never zero. When nothing matches, the reply "
    "carries no_matches and suggestions listing the real catalogue names to retry with."
)

GET_SKU = (
    "Everything known about one SKU: facts with units and value ranges, decoded "
    "ordering code, and optionally brochure text and sources. The ordering code may be "
    "partial; when it resolves to a different code the response reports the resolved "
    "code and other candidates. " + NAME_MATCHING
)

COMPARE_SKUS = (
    "Side-by-side specification table for 2–10 SKUs identified by ORDERING CODE. It "
    "does not accept family or product-line names — run product_search first to turn a "
    "name into ordering codes. Codes that match nothing are returned in "
    "unresolved_sku_codes. Spec IDs also match their labels. Use for straightforward "
    "comparison instead of analytics_query. Empty cells mean the spec is not published."
)

SEARCH_DOCUMENTS = (
    "Semantic search over brochure text. Use ONLY for qualitative questions: how a "
    "feature works, application suitability, or what a standard requires. Never use it "
    "to find, rank, or compare numeric ratings. Always pass category or family. "
    + NAME_MATCHING + " Results shared across many SKUs are family-level text, not "
    "one SKU's specification."
)

ANALYTICS_QUERY = (
    "Delegate complex quantitative analysis across catalogue views, including "
    "multi-step aggregates, joins, subqueries, distributions, rankings, and pivots "
    "over many products. The analytics sub-agent can run several SQL queries and "
    "returns a factual summary with supporting numeric evidence, but no conclusions "
    "or recommendations. Call it once with the complete analytical question. For "
    "straightforward comparison of 2–10 named SKUs use compare_skus."
)
