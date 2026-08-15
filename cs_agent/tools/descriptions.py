"""Tool description strings — ship as written; they steer tool choice."""

NAME_MATCHING = (
    "Names are matched loosely: case, spacing, hyphens versus dashes, and straight "
    "versus curly quotes are all ignored, and the words you give may appear in any "
    "order, so 'winmaster 2', 'ACB - WiNmaster 2' and 'WiNmaster2' all reach the "
    "'ACB – WiNmaster 2' catalogue entries. Give the words you know rather than "
    "guessing punctuation."
)

LIST_CANONICAL_SPECS = (
    "List specification IDs for a family with units, value kinds, SKU counts, "
    "composite counts, and observed bounds. Use spec_id_contains to discover topic "
    "vocabulary. Call before product_search filters; never guess spec IDs."
)

TAXONOMY_BROWSE = (
    "Walk the 2–4 level C&S catalogue path one level at a time, returning published "
    "descriptions, URLs, leaf status and SKU counts. _no_category entries are separated "
    "as uncategorised pricelist sections. Browsing alone is not a product answer."
)

PRODUCT_SEARCH = (
    "Find SKUs by specification filters, ordering-code facets, or name and code "
    "fragments, path, market segment, price status, or chunk presence. This is the "
    "PRIMARY tool for any number, rating, range, or "
    "superlative, and the way to turn a product-line name into ordering codes. "
    + NAME_MATCHING + " Spec IDs also match their labels, so 'breaking capacity' "
    "finds breaking_capacity_ka. Range specs use their min/max bounds. Missing "
    "specifications mean not published, never zero. composite_excluded values are "
    "unknown, not ruled out. Read widening_hint before concluding no product exists. "
    "price_status must be a list such as [\"listed\"], not a bare string. Hits include "
    "price_inr when a single listed figure is quotable, cheapest first. For the cheapest "
    "or dearest product across a family, prefer analytics_query so the ranking covers "
    "every SKU, not just the first page of hits."
)

GET_SKU = (
    "Everything known about one SKU: facts with units and value ranges, decoded "
    "ordering code, source references, extraction missing/confidence, and optionally "
    "chunks, price and peers. Resolve user-entered codes with resolve_product first."
)

COMPARE_SKUS = (
    "Side-by-side specification table for 2–10 SKUs identified by ORDERING CODE. It "
    "does not accept family or product-line names — run product_search first to turn a "
    "name into ordering codes. Codes that match nothing are returned in "
    "unresolved_sku_codes. Spec IDs also match their labels. Use for straightforward "
    "comparison instead of analytics_query. Empty cells mean the spec is not published."
)

SEARCH_DOCUMENTS = (
    "Semantic search over qualitative catalogue text, filterable by path, family, SKU, "
    "and chunk_type. Never use it for numeric ratings. Always pass family or path. "
    "Falls back to lexical search and reports its mode."
)

RESOLVE_PRODUCT = (
    "Resolve a product code, alias, partial code, misspelling, or description to real "
    "SKU codes. Always use this before SKU-specific tools when the user typed the code."
)

GET_PRICE_DETAIL = (
    "Retrieve provenance-aware pricing for up to 10 SKUs. Respect price_status; never "
    "quote multiple_variants or observations whose context names another code."
)

GET_PEER_GROUP = (
    "Return a SKU's catalogue peer set, comparable_on axes, related codes, and decoded "
    "differences. Use for shortlists and like-for-like comparison."
)

ANALYTICS_QUERY = (
    "Delegate complex quantitative analysis across catalogue views, including "
    "multi-step aggregates, joins, subqueries, distributions, rankings, and pivots "
    "over many products. The analytics sub-agent can run several SQL queries and "
    "returns a factual summary with supporting numeric evidence, but no conclusions "
    "or recommendations. Call it once with the complete analytical question. For "
    "straightforward comparison of 2–10 named SKUs use compare_skus."
)
