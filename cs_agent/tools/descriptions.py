"""Tool description strings — ship as written; they steer tool choice."""

NAME_MATCHING = (
    "Names are matched loosely: case, spacing, hyphens versus dashes, and straight "
    "versus curly quotes are all ignored, and the words you give may appear in any "
    "order, so 'winmaster 2', 'ACB - WiNmaster 2' and 'WiNmaster2' all reach the "
    "'ACB – WiNmaster 2' catalogue entries. Give the words you know rather than "
    "guessing punctuation."
)

LIST_CANONICAL_SPECS = (
    "List the specification IDs a scope SHARES, with units, value kinds, and "
    "per-group SKU counts and observed bounds. family accepts a string or a list "
    "of names (OR); path is one prefix (AND down the tree). Pass every family "
    "already in hand in a single call rather than looping one family at a time. "
    "Across several families it returns only the spec IDs EVERY one of them "
    "publishes, because only those can be compared: specs holds one row per "
    "shared spec_id, and by_group gives that family's own sku_count and observed "
    "min/max, so you can see where the ranges actually differ. IDs that only some "
    "families publish are named in not_shared against the families that have "
    "them, never returned in full — call again with that one family to see one. "
    "group_by defaults to family; set it to a level column to intersect across "
    "divisions or product groups instead. Empty specs with a populated not_shared "
    "means the families share no vocabulary, not that the catalogue is empty; a "
    "name matching no family is families_not_found. Use spec_id_contains to "
    "discover topic vocabulary. Call before product_search filters; never guess "
    "spec IDs — ask only for IDs this returned."
)

# The only values market_segment accepts. Assigned per division in the source
# catalogue, so they select a broad slice of the tree rather than a product
# audience; a tool that does not say so gets called with "Domestic" and returns
# nothing, which is what sent one measured run walking the taxonomy by hand.
MARKET_SEGMENTS = (
    "Agriculture, Commercial, Distribution & Transmission, Industries, "
    "Infrastructure, Original Equipment Manufacturers (OEM), Residential"
)

SEGMENT_NOTE = (
    "market_segment filters on the catalogue's own audience tag and accepts "
    f"only these values: {MARKET_SEGMENTS}. The tag is assigned per division, "
    "so it says where the catalogue files a product, not everywhere it can be "
    "used — Residential returns Final Distribution Products, and products "
    "elsewhere whose descriptions mention residential use are not included."
)
CATALOGUE_MAP = (
    "Find where something sits in the catalogue without walking the tree. "
    "Fuzzy-matches path_text against the full division > group > subgroup > "
    "family path, and market_segment against the audience tag, then returns "
    "one row per matching family broken down by the level columns themselves — "
    "division, product_group, product_subgroup, product_range — with the SKU "
    "count, published description and URL. A level the branch never reaches is "
    "omitted rather than returned as 'N/A'. Each row also carries those same "
    "values as a `path` list, which is exactly what taxonomy_browse and "
    "product_search take, so a follow-up call needs no guessing. Needs "
    "path_text, market_segment, or both — neither "
    "is an error. This is the FASTEST way to answer 'what X products do you "
    "have' and the right first call when a product-line name is known but its "
    "path is not: catalogue_map(path_text='wintrip') returns all five WiNtrip "
    "families in one call. " + SEGMENT_NOTE + " Punctuation and spacing do not "
    "have to match, so 'wintrip s modular' finds \u2018S\u2019 Modular. "
    "total_skus counts distinct SKUs across matched families and is exact, not "
    "a sample. Families the pricelist names but the published taxonomy never "
    "placed — RCBO among them — come back under uncategorised with no path; "
    "reach their SKUs with product_search(family=...). An empty result carries "
    "closest_paths or known_market_segments, so read those instead of guessing "
    "again. It returns no ordering codes: use product_search for those."
)

TAXONOMY_BROWSE = (
    "Walk the 2–4 level C&S catalogue path one level at a time, returning published "
    "descriptions, URLs, leaf status and SKU counts. _no_category entries are separated "
    "as uncategorised pricelist sections. include_facets adds ordering-code axis values "
    "for the whole branch; near the root that list is capped to the most common ones, "
    "so read facets_truncated and browse deeper rather than concluding a variant does "
    "not exist. path is a LIST of literal division / product_group / "
    "product_subgroup / product_range values, never a URL slug or brochure wording; "
    "call it with path=[] — the empty list, not an empty string — to list the "
    "divisions, then work down from the children it returns. "
    + SEGMENT_NOTE +
    " To find a branch by name without knowing its path, or to see every "
    "branch carrying a segment at once, call catalogue_map instead of "
    "walking the tree."
)

PRODUCT_SEARCH = (
    "Find SKUs by specification filters, ordering-code facets, or name and code "
    "fragments, path, market segment, price status, or chunk presence. This is the "
    "PRIMARY tool for any number, rating, range, or "
    "superlative, and the way to turn a product-line name into ordering codes. "
    "family accepts a string or a list of names (OR across families); path remains "
    "one prefix, not an OR of levels. Pass all known families in one call. "
    "Anything true of every hit — family, path, the product page url — is "
    "stated once in a `scope` object beside the hits rather than repeated on "
    "each of them; a field that differs between hits stays on the hits. So "
    "grouped or not you can always tell which product a specification belongs "
    "to: read the hit first, then `scope`. When the scope spans several "
    "families, return_specs attaches only the specifications ALL of them "
    "publish — an empty cell would otherwise read as a product difference "
    "rather than a gap in the catalogue — and the rest are named in "
    "specs_not_shared against the families that do publish them. For "
    "counts across families or a path level, set group_by to family, division, "
    "product_group, product_subgroup, or product_range — that returns every "
    "in-scope group including zeros. A zero with spec_present true means the spec "
    "is published but no SKU matched; spec_present false means the spec does not "
    "belong to that group. Zeros are searched-and-none, not forgotten. group_by "
    "requires family and/or path. Omit group_by for a shortlist of hits: limit "
    "then caps the hit list globally; with group_by, limit is the sample per "
    "group. "
    + NAME_MATCHING + " Spec IDs also match their labels, so 'breaking capacity' "
    "finds breaking_capacity_ka. Attached specifications are keyed by spec_id and "
    "carry no label: you named the ids, and list_canonical_specs is where their "
    "published labels live. Range specs use their min/max bounds. Missing "
    "specifications mean not published, never zero. composite_excluded values are "
    "unknown, not ruled out. Read widening_hint before concluding no product exists. "
    "price_status must be a list such as [\"listed\"], not a bare string. "
    "market_segment accepts only: " + MARKET_SEGMENTS + ". Hits carry "
    "price_inr with a price_quotable flag, cheapest quotable first; a figure whose "
    "price_quotable is false must not be quoted, so call get_price_detail before "
    "stating any price. For the cheapest or dearest product across a family, prefer "
    "analytics_query so the ranking covers every SKU, not just the first page of hits."
)

GET_SKU = (
    "Everything known about one SKU: facts with units and value ranges, decoded "
    "ordering code, source references, extraction missing/confidence, and optionally "
    "chunks, price and peers. A fact is identified by its spec_id and carries no "
    "label and no restating sentence — the value_display, unit and source_of_truth "
    "beside it are the whole fact. Resolve user-entered codes with resolve_product "
    "first."
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
    "Falls back to lexical search when the catalogue carries no embeddings: a hit "
    "with a distance came from the semantic index and one without it from the "
    "lexical one, and score is comparable only between hits of the same call. "
    "Long passages are returned head-first and marked truncated; retrieve the "
    "whole passage with get_sku chunks when the part you need was cut."
)

RESOLVE_PRODUCT = (
    "Resolve a product code, alias, partial code, misspelling, or description to real "
    "SKU codes. The sku_code it returns is the one to order by and the one to hand "
    "to every other tool; match_role says whether it was reached as a code, a "
    "canonical spelling, an alias or a description, and an alias_note explains an "
    "alternate published spelling. Always use this before SKU-specific tools when "
    "the user typed the code."
)

GET_PRICE_DETAIL = (
    "Retrieve provenance-aware pricing for up to 10 SKUs. Respect price_status: never "
    "quote a multiple_variants figure, and report por as price on request. quotable "
    "says whether a figure may be given at all. A price_sibling_code means the figure "
    "was read from a pricelist table headed by that other ordering code — report it "
    "together with the caveat, not as an unqualified price."
)

GET_PEER_GROUP = (
    "Return a SKU's catalogue peer set, comparable_on axes, related codes, and decoded "
    "differences. Each peer's decoded ordering code is one entry per axis holding "
    "that axis's meaning, and the family the whole group sits in is stated once "
    "in `scope`. Use for shortlists and like-for-like comparison. peer_count is the "
    "true size of the group; peers is a page of it. When a truncated note is present "
    "the group is larger than the list, so never say it has only the SKUs shown — "
    "reach a specific peer with product_search instead."
)

ANALYTICS_QUERY = (
    "Delegate complex quantitative analysis across catalogue views, including "
    "multi-step aggregates, joins, subqueries, distributions, rankings, and pivots "
    "over many products. The analytics sub-agent can run several SQL queries and "
    "returns a factual summary with supporting numeric evidence, but no conclusions "
    "or recommendations. Call it once with the complete analytical question. Pass "
    "family whenever the question sits inside one product area: it scopes the "
    "specification vocabulary the SQL writer is given, which makes the query more "
    "accurate. For straightforward comparison of 2–10 named SKUs use compare_skus."
)
