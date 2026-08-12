CREATE OR REPLACE FUNCTION in_use.safe_num(t text) RETURNS double precision
LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN t ~ '^-?[0-9]+(\.[0-9]+)?$' THEN t::double precision END
$$;

DROP MATERIALIZED VIEW IF EXISTS in_use.mv_facet;
DROP MATERIALIZED VIEW IF EXISTS in_use.mv_spec_registry;
DROP MATERIALIZED VIEW IF EXISTS in_use.mv_fact;
DROP MATERIALIZED VIEW IF EXISTS in_use.mv_sku;

CREATE MATERIALIZED VIEW in_use.mv_sku AS
SELECT DISTINCT ON (product_id)
  product_id,
  product->>'sku_code' AS sku_code,
  product->>'family' AS family,
  taxonomy->>'category' AS category,
  product->>'url' AS url,
  taxonomy->'decoded' AS decoded,
  details->'completeness' AS completeness,
  details->'sources' AS sources,
  COALESCE((details->'completeness'->>'has_price')::boolean, false) AS has_price,
  jsonb_array_length(COALESCE(details->'facts', '[]'::jsonb)) AS fact_count
FROM in_use.product_chunks
WHERE is_active AND product_id IS NOT NULL
ORDER BY product_id, id;

CREATE UNIQUE INDEX mv_sku_product_id_idx ON in_use.mv_sku (product_id);
CREATE UNIQUE INDEX mv_sku_sku_code_idx ON in_use.mv_sku (sku_code);
CREATE INDEX mv_sku_category_family_idx ON in_use.mv_sku (category, family);

CREATE MATERIALIZED VIEW in_use.mv_fact AS
SELECT
  s.sku_code,
  s.family,
  s.category,
  f->>'canonical_spec_id' AS spec_id,
  f->>'spec_label' AS spec_label,
  NULLIF(f->>'unit', '') AS unit,
  in_use.safe_num(f->>'value') AS value_num,
  in_use.safe_num(f->>'value_min') AS value_min,
  in_use.safe_num(f->>'value_max') AS value_max,
  f->>'value_display' AS value_display,
  f->>'value_kind' AS value_kind,
  f->>'source_of_truth' AS source_of_truth,
  COALESCE((f->>'derived')::boolean, false) AS derived,
  f->>'fact_sentence' AS fact_sentence
FROM in_use.mv_sku s
JOIN in_use.product_chunks pc ON pc.product_id = s.product_id
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(pc.details->'facts', '[]'::jsonb)) AS f
WHERE pc.id = (
  SELECT min(x.id)
  FROM in_use.product_chunks x
  WHERE x.product_id = s.product_id AND x.is_active
);

CREATE INDEX mv_fact_spec_value_idx ON in_use.mv_fact (spec_id, value_num);
CREATE INDEX mv_fact_sku_code_idx ON in_use.mv_fact (sku_code);
CREATE INDEX mv_fact_category_spec_idx ON in_use.mv_fact (category, spec_id);

CREATE MATERIALIZED VIEW in_use.mv_spec_registry AS
SELECT
  category,
  spec_id,
  mode() WITHIN GROUP (ORDER BY spec_label) AS spec_label,
  mode() WITHIN GROUP (ORDER BY unit) AS unit,
  mode() WITHIN GROUP (ORDER BY value_kind) AS value_kind,
  count(DISTINCT sku_code) AS sku_count,
  min(COALESCE(value_min, value_num)) AS observed_min,
  max(COALESCE(value_max, value_num)) AS observed_max
FROM in_use.mv_fact
GROUP BY category, spec_id;

CREATE UNIQUE INDEX mv_spec_registry_category_spec_idx
  ON in_use.mv_spec_registry (category, spec_id);

CREATE MATERIALIZED VIEW in_use.mv_facet AS
SELECT
  category,
  family,
  d.key AS axis,
  COALESCE(d.value->>'meaning', d.value->>'code') AS meaning,
  d.value->>'code' AS code,
  count(*) AS sku_count
FROM in_use.mv_sku s
CROSS JOIN LATERAL jsonb_each(
  CASE
    WHEN jsonb_typeof(s.decoded) = 'object' THEN s.decoded
    ELSE '{}'::jsonb
  END
) AS d
GROUP BY 1, 2, 3, 4, 5;

CREATE INDEX mv_facet_category_family_idx
  ON in_use.mv_facet (category, family, axis);
