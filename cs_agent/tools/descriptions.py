"""Tool descriptions exposed to the product agent."""

LIST_CATEGORIES = """List the available product taxonomy categories. Use this first when the user's requested category is unknown. Returns category identifiers, names, and descriptions."""

LIST_FACTS = """List canonical facts available for one exact taxonomy category, including units, value types, and required condition keys. Use before product_search so filters use valid fact identifiers and conditions."""

PRODUCT_SEARCH = """Search product families in one taxonomy category using canonical-fact filters. Every conditional fact filter must include all condition keys returned by list_facts. Returns matching families and their evidence-bearing facts."""

GET_PRODUCT = """Get one product family by exact family_id, including its variants and canonical facts. Use only after discovering the family_id from another tool."""

SEARCH_DOCUMENTS = """Search synthetic brochure text by keywords, optionally restricted to a family_id. Returns quotable chunks with document names and page numbers; do not use brochure prose as a substitute for canonical numeric facts."""

ANALYTICS_QUERY = """Answer an aggregate or comparative catalogue question through the read-only analytics subgraph. Use for counts, grouping, extrema, and multi-row comparisons rather than individual product lookup."""
