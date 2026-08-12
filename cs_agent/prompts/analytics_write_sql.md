Write ONE PostgreSQL SELECT statement answering the question below.

Views available (read-only):

  in_use.mv_sku(sku_code, family, category, url, decoded jsonb,
                completeness jsonb, has_price bool, fact_count int)
  in_use.mv_fact(sku_code, family, category, spec_id, spec_label, unit,
                 value_num, value_min, value_max, value_display, value_kind,
                 source_of_truth, derived, fact_sentence)
  in_use.mv_spec_registry(category, spec_id, spec_label, unit, value_kind,
                          sku_count, observed_min, observed_max)
  in_use.mv_facet(category, family, axis, code, meaning, sku_count)

mv_fact is long-format: one row per (sku_code, spec_id). Pivot comparisons with FILTER.

Spec IDs in scope:
{spec_registry}

RULES
- One statement. SELECT only.
- Use range-aware predicates:
    gte x -> COALESCE(value_max, value_num) >= x
    lte x -> COALESCE(value_min, value_num) <= x
    eq x  -> x BETWEEN COALESCE(value_min, value_num)
                    AND COALESCE(value_max, value_num)
- value_num is NULL for text and set specs; use value_display.
- price_inr may have value_display 'POR'. Exclude it explicitly from numeric ranking
  and count POR rows separately.
- A missing spec row is not zero. Use LEFT JOIN and report NULL.
- Identify products by sku_code. Never return product_id.
- Return the columns requested in output_shape, using those names.

Output only the SQL. No explanation, no fences.
