Write the final answer using only these specialist reports:
{reports_json}

Assumptions and user-supplied parameters:
{assumptions}

Rules:
1. Every specification you state must appear in a report. If it is not there,
   either omit it or mark it clearly as general engineering practice rather than a C&S
   specification.
2. Cite as: SKU code, then how the value is known:
   - source_of_truth "pricelist_table" → "(C&S pricelist)"
   - source_of_truth "code_grammar" → "(derived from ordering code)"
   - brochure_md → cite the markdown filename without a page
   - pricelist_pdf → cite its supplied page
   - product_page_url → cite the supplied URL
3. Report range-valued specs as ranges, not a single figure.
4. Report conditional ratings with their condition. If evidence has no condition,
   write "condition not specified in source" rather than assuming one.
5. A spec listed in extraction.missing is "not published by C&S", never zero.
6. Respect all seven price statuses. Never quote a multiple_variants figure: say the
   pricelist row covers several variants so no single price applies. Report por as
   price on request and point to the nearest C&S branch office. When a price carries
   price_sibling_code, quote the figure and add one short sentence saying it was read
   from a pricelist table headed by that other ordering code and should be confirmed
   with C&S. State that prices are MRP inclusive of GST.
7. Separate catalogue facts from general engineering knowledge. Use two clearly
   labelled sections when the answer contains both.
8. Open by listing the assumptions you worked from, if any. Values in known_params
   were supplied by the user — do not claim they were missing, and use them when
   sizing or selecting products.
9. If you recommend a configuration with more than one component (breaker plus trip
   unit, contactor plus accessory), add: "Component compatibility has not been verified
   against the accessory matrix — confirm with C&S before ordering."
10. If the catalogue does not cover part of the question, say which part.
11. Neutral, professional tone. No sales language.
12. Answer at the breadth the question was asked at. A report that names families
    without ordering codes is an overview, and the answer should read like one: name
    each range, say in a line what it is for and the span it covers, and stop. Do not
    pad it with codes, ratings or price and compatibility notes the user did not ask
    for. Add a caveat only when it bears on what was actually asked. Leave out general
    engineering commentary on what the product category does — rule 7 would make you
    split it into its own section, and at this length that costs more than it adds.
13. A family's description must be C&S's published text, quoted. When the report's
    description field for a family is null or absent, write only the family name and
    its SKU count, then either stop or state that C&S publishes no description for
    that range. Characterising it yourself — what it suits, who it is for, where it
    sits in the line-up — is invention, however reasonable it sounds. An uneven list
    where one family has a description and another does not is the correct output.
    Spell every family and category exactly as the report spells it. Do not
    substitute a wording taken from a URL, a brochure heading, or the name the range
    goes by in the trade — those differ from what C&S publishes as the category.
14. Close with the report's follow_up_questions when it carries any — a short line
    offering to go further, then the questions. Ask, do not assume: the user is
    choosing what to narrow to, so do not answer them yourself or guess which one
    they meant. Never describe the machinery while doing it. The user does not know
    what a report, a depth, a stage or a specialist is, so write "I can pull the
    ordering codes for any of these" — never "not provided at this overview depth"
    or "not in the report". What C&S does not publish is a fact about the product
    and belongs in the answer; what the pipeline did not do is not.
15. Before answering, silently verify every number, unit, ordering code, and range
    against the reports. There is no downstream validation pass: omit any
    claim that the evidence does not directly support.
