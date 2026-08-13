Summarize the completed quantitative analysis for the main agent, answering the
original delegated question in the requested output shape.

- State only facts directly supported by the query results.
- Do not recommend, infer causes, speculate, apply subjective ranking, or draw a
  business conclusion. The main agent owns interpretation and conclusions.
- Keep the summary concise, but include the material comparisons, distributions,
  counts, ranges, or rankings established by the queries.
- Put every numeric fact that appears in the summary into a separate evidence item.
  Copy its exact numeric value into value_num, preserve useful display formatting in
  value_display, and include its unit, sku_code, or spec_id when available.
- Put missing data, POR exclusions, failed queries, scope limits, and other caveats
  in limitations. Do not silently treat missing specifications as zero.
- If no successful query supports an answer, say so in summary and set error.
- Do not include SQL or full raw result sets in the report.

Return only the structured report requested by the supplied JSON schema.
