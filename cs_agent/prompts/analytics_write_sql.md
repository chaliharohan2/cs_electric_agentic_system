Write ONE SQLite SELECT answering the question.

Tables:
  sku_fact — ONE ROW PER (sku_code, spec_id). A product with many specifications occupies
             that many rows, and ALL of its metadata (family, path, price, decode) repeats
             identically on every one of them. Rows with is_sentinel = 1 are SKUs that
             have no facts at all; their spec columns are NULL.
  chunk    — brochure text, one row per (sku_code, chunk_type).

Key columns:
  sku_code, canonical_code, family, division, product_group, product_subgroup,
  product_range, path_depth, path_text, is_no_category,
  price_status, price_quotable, price_inr, price_context_ok,
  spec_id, spec_label, unit, value_num, value_min, value_max, value_display,
  value_kind, is_canonical_spec, source_of_truth, fact_sentence

COUNTING PRODUCTS — read this first.
  Never write count(*) to count products. It counts fact rows and overstates by roughly
  20–30x. Use count(DISTINCT sku_code).
  To list products with their metadata, collapse to one row per product:
     WHERE row_id IN (SELECT min(row_id) FROM sku_fact GROUP BY sku_code)
  Do not use SELECT DISTINCT across the wide column list; it is slow on this table.

DIALECT
- SQLite, not PostgreSQL. FILTER is supported. There is no mode(), no regexp_replace,
  no array type, and no ILIKE (LIKE is already case-insensitive for ASCII).
- JSON columns (decoded, comparable_on, related_codes, market_segments,
  price_observations, spec_ids, chunk_types, extraction_missing) are TEXT. Read with
  json_extract(col, '$.key'); expand arrays with json_each(col).

RULES
- One statement. SELECT only.
- Range predicates:
    gte x -> COALESCE(value_max, value_num) >= x
    lte x -> COALESCE(value_min, value_num) <= x
    eq  x -> x BETWEEN COALESCE(value_min, value_num) AND COALESCE(value_max, value_num)
- value_kind 'composite' has all numerics NULL and matches no numeric predicate. When
  filtering numerically, also return a count of the composite rows excluded.
- Several spec filters at once need GROUP BY sku_code HAVING count(DISTINCT spec_id) = n.
- 'N/A' in a level column means the branch has no such level. Exclude it explicitly
  rather than treating it as a category.
- Never aggregate price where price_status = 'multiple_variants'. Exclude 'por' from
  numeric ranking and count those separately.
- Identify products by sku_code. Never return product_id or row_id.

Specs in scope:
{spec_registry}

Output only the SQL. No explanation, no fences.
