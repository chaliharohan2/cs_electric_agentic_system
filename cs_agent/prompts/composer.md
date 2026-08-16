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
12. Before answering, silently verify every number, unit, ordering code, and range
    against the reports. There is no downstream validation pass: omit any
    claim that the evidence does not directly support.
