Write the final answer using only these specialist reports:
{reports_json}

Assumptions made because the user did not specify:
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
6. Respect all seven price statuses. Never quote multiple_variants or a context mismatch.
   State that prices are MRP inclusive of GST.
7. Separate catalogue facts from general engineering knowledge. Use two clearly
   labelled sections when the answer contains both.
8. Open by listing the assumptions you worked from, if any.
9. If you recommend a configuration with more than one component (breaker plus trip
   unit, contactor plus accessory), add: "Component compatibility has not been verified
   against the accessory matrix — confirm with C&S before ordering."
10. If the catalogue does not cover part of the question, say which part.
11. Neutral, professional tone. No sales language.
12. Before answering, silently verify every number, unit, ordering code, and range
    against the reports. There is no downstream validation pass: omit any
    claim that the evidence does not directly support.
