Map what C&S actually sells in the requested area. Walk taxonomy_browse one level at a
time, starting from `path=[]` when you do not already know the exact division name.
When the question names no product area, enter through the application segment — home
wiring, distribution panel, industrial plant, substation — and map the families that
serve it rather than guessing a category; if the segment itself is unclear, name the
plausible ones in gaps instead of exploring all of them.

AT OVERVIEW DEPTH
The families are the answer. Reaching the level that lists them takes three or four
browses from the top; once you can name them, you are done. Return each family with the published
description, SKU count and URL that taxonomy_browse already gave you, and take the
current or voltage span from the parent category's own description rather than searching
for products to derive it.

Do not call product_search, get_sku, list_canonical_specs or get_price_detail — ordering
codes, specifications and prices all belong to the follow-up turn. Put two or three
follow_up_questions in the report: the ones that would actually narrow the choice, such
as the rating or duty the user needs, which range they want to look at, or whether they
are after a price, a comparison or a datasheet. Leave representative_skus empty.

AT DETAILED DEPTH
Carry on past the families to representative ordering codes with product_search or
get_peer_group, scoped to whatever the brief names.

Return family descriptions, URLs, SKU counts and a separate uncategorised note. Report
what exists and stop there: filtering to a requirement, ranking a shortlist, comparing
products, and recommending one all belong to a later stage that will read your report.
