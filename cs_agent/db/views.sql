CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE OR REPLACE FUNCTION in_use.safe_num(t text) RETURNS double precision
LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN t ~ '^-?[0-9]+(\.[0-9]+)?$' THEN t::double precision END
$$;

-- Ordering codes are printed with inconsistent case, spacing, and hyphenation
-- (CG24025W / CG 24 025 W / cg-24025-w). Fold them the same way the runtime
-- resolver does in cs_agent/backends/sqlite.py::_normalize_code.
CREATE OR REPLACE FUNCTION in_use.norm_code(t text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
  SELECT lower(regexp_replace(COALESCE(t, ''), '[^A-Za-z0-9]', '', 'g'))
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'in_use'
      AND table_name = 'product_chunks'
      AND column_name = 'content_tsv'
  ) THEN
    ALTER TABLE in_use.product_chunks
      ADD COLUMN content_tsv tsvector
      GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
  END IF;
END $$;

DO $$
DECLARE
  embedding_type text;
  populated bigint;
BEGIN
  SELECT format_type(a.atttypid, a.atttypmod)
  INTO embedding_type
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'in_use' AND c.relname = 'product_chunks'
    AND a.attname = 'embedding' AND NOT a.attisdropped;

  IF embedding_type IS DISTINCT FROM 'vector(768)' THEN
    SELECT count(*) INTO populated
    FROM in_use.product_chunks WHERE embedding IS NOT NULL;
    IF populated > 0 THEN
      RAISE EXCEPTION
        'Refusing to change embedding from % to vector(768): % rows are populated',
        embedding_type, populated;
    END IF;
    ALTER TABLE in_use.product_chunks
      ALTER COLUMN embedding TYPE vector(768)
      USING NULL::vector(768);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS product_chunks_content_tsv_idx
  ON in_use.product_chunks USING gin (content_tsv);

DROP MATERIALIZED VIEW IF EXISTS in_use.mv_chunk_index;
DROP MATERIALIZED VIEW IF EXISTS in_use.mv_facet;
DROP MATERIALIZED VIEW IF EXISTS in_use.mv_spec_registry;
DROP MATERIALIZED VIEW IF EXISTS in_use.mv_source;
DROP MATERIALIZED VIEW IF EXISTS in_use.mv_price;
DROP MATERIALIZED VIEW IF EXISTS in_use.mv_fact;
DROP MATERIALIZED VIEW IF EXISTS in_use.mv_code_alias;
DROP MATERIALIZED VIEW IF EXISTS in_use.mv_sku;

CREATE MATERIALIZED VIEW in_use.mv_sku AS
SELECT DISTINCT ON (product_id)
  product_id,
  product->>'sku_code' AS sku_code,
  COALESCE(product->>'canonical_code', product->>'sku_code') AS canonical_code,
  product->>'family' AS family,
  product->>'description' AS description,
  product->>'url' AS url,
  product->>'price_status' AS price_status,
  product->>'peer_group' AS peer_group,
  product->'decoded' AS decoded,
  product->'attributes' AS attributes,
  product->'comparable_on' AS comparable_on,
  product->'related_codes' AS related_codes,
  product->'market_segments' AS market_segments,
  product->'also_published_as' AS also_published_as,
  product->>'alias_reason' AS alias_reason,
  product->'price_observations' AS price_observations,
  taxonomy->'path' AS path,
  COALESCE((taxonomy->>'depth')::int, jsonb_array_length(
    CASE WHEN jsonb_typeof(taxonomy->'path') = 'array' THEN taxonomy->'path' ELSE '[]'::jsonb END
  )) AS depth,
  array_to_string(
    ARRAY(
      SELECT jsonb_array_elements_text(
        CASE WHEN jsonb_typeof(taxonomy->'path') = 'array' THEN taxonomy->'path' ELSE '[]'::jsonb END
      )
    ), ' > '
  ) AS path_text,
  taxonomy->'path'->>0 AS path_l1,
  taxonomy->'path'->>1 AS path_l2,
  taxonomy->'path'->>2 AS path_l3,
  (taxonomy->'path'->>0 = '_no_category') AS is_no_category,
  taxonomy->'headings' AS headings,
  details->'spec_ids' AS spec_ids,
  details->'derived' AS derived,
  details->'sources' AS sources,
  details->'extraction' AS extraction,
  details->'extraction'->'missing' AS extraction_missing,
  details->'extraction'->>'confidence' AS extraction_confidence,
  jsonb_array_length(
    CASE WHEN jsonb_typeof(details->'facts') = 'array' THEN details->'facts' ELSE '[]'::jsonb END
  ) AS fact_count
FROM in_use.product_chunks
WHERE is_active AND product_id IS NOT NULL
ORDER BY product_id, id;

CREATE UNIQUE INDEX mv_sku_product_id_idx ON in_use.mv_sku (product_id);
CREATE UNIQUE INDEX mv_sku_sku_code_idx ON in_use.mv_sku (sku_code);
CREATE INDEX mv_sku_family_idx ON in_use.mv_sku (family);
CREATE INDEX mv_sku_path_idx ON in_use.mv_sku (path_l1, path_l2, path_l3);
CREATE INDEX mv_sku_family_trgm_idx ON in_use.mv_sku USING gin (family gin_trgm_ops);
CREATE INDEX mv_sku_path_text_trgm_idx ON in_use.mv_sku USING gin (path_text gin_trgm_ops);
CREATE INDEX mv_sku_market_segments_idx
  ON in_use.mv_sku USING gin (
    (CASE WHEN jsonb_typeof(market_segments) = 'array' THEN market_segments ELSE '[]'::jsonb END)
    jsonb_path_ops
  );

CREATE MATERIALIZED VIEW in_use.mv_code_alias AS
SELECT product_id, sku_code AS code, 'sku'::text AS role
FROM in_use.mv_sku
UNION
SELECT product_id, canonical_code, 'canonical'
FROM in_use.mv_sku
WHERE canonical_code IS DISTINCT FROM sku_code
UNION
SELECT s.product_id, alias.code, 'alias'
FROM in_use.mv_sku s
CROSS JOIN LATERAL jsonb_array_elements_text(
  CASE
    WHEN jsonb_typeof(s.also_published_as) = 'array' THEN s.also_published_as
    ELSE '[]'::jsonb
  END
) AS alias(code);

CREATE INDEX mv_code_alias_code_idx ON in_use.mv_code_alias (code);
CREATE INDEX mv_code_alias_code_trgm_idx
  ON in_use.mv_code_alias USING gin (code gin_trgm_ops);
CREATE INDEX mv_code_alias_product_id_idx ON in_use.mv_code_alias (product_id);
-- Drives mv_price's pricelist-header lookup; without it that becomes a scan of
-- every alias for every price observation.
CREATE INDEX mv_code_alias_norm_code_idx
  ON in_use.mv_code_alias (in_use.norm_code(code));

CREATE MATERIALIZED VIEW in_use.mv_fact AS
SELECT
  s.product_id,
  s.sku_code,
  s.family,
  s.path_text,
  f->>'canonical_spec_id' AS spec_id,
  f->>'spec_label' AS spec_label,
  NULLIF(f->>'unit', '') AS unit,
  COALESCE((f->>'canonical')::boolean, false) AS is_canonical_spec,
  in_use.safe_num(f->>'value') AS value_num,
  in_use.safe_num(f->>'value_min') AS value_min,
  in_use.safe_num(f->>'value_max') AS value_max,
  f->>'value_display' AS value_display,
  f->>'value_kind' AS value_kind,
  f->>'source_of_truth' AS source_of_truth,
  CASE WHEN jsonb_typeof(f->'source') = 'object'
       THEN f->'source'->>'pdf' END AS source_pdf,
  CASE WHEN jsonb_typeof(f->'source') = 'object'
       THEN in_use.safe_num(f->'source'->>'page')::int END AS source_page,
  CASE WHEN jsonb_typeof(f->'source') = 'string'
            AND f->>'source' <> 'brochure'
       THEN f->>'source' END AS source_heading,
  f->>'fact_sentence' AS fact_sentence
FROM in_use.mv_sku s
JOIN in_use.product_chunks pc ON pc.product_id = s.product_id
CROSS JOIN LATERAL jsonb_array_elements(
  CASE
    WHEN jsonb_typeof(pc.details->'facts') = 'array' THEN pc.details->'facts'
    ELSE '[]'::jsonb
  END
) AS f
WHERE pc.id = (
  SELECT min(x.id)
  FROM in_use.product_chunks x
  WHERE x.product_id = s.product_id AND x.is_active
);

CREATE INDEX mv_fact_spec_value_idx ON in_use.mv_fact (spec_id, value_num);
CREATE INDEX mv_fact_product_id_idx ON in_use.mv_fact (product_id);
CREATE INDEX mv_fact_sku_code_idx ON in_use.mv_fact (sku_code);
CREATE INDEX mv_fact_family_spec_idx ON in_use.mv_fact (family, spec_id);
CREATE INDEX mv_fact_value_kind_idx ON in_use.mv_fact (value_kind);

-- `context` is the pricelist TABLE header, not the SKU's own row:
-- "<first cell> | [HSN Code: NNNN] | <section title>". Only 60 of 10,477
-- observations mention their own code, so "does the header name me" answers
-- "am I the first row of this table" — useless as a quotability test, and it
-- previously left exactly one SKU in 9,115 quotable.
--
-- What the header does reveal is the multi-column price-binding defect: when
-- its first cell is the ordering code of a DIFFERENT product, this figure was
-- read from a table keyed on that sibling and may not belong to this SKU.
-- That is surfaced as context_sibling_code for disclosure, and no longer
-- suppresses the price.
CREATE MATERIALIZED VIEW in_use.mv_price AS
WITH observation AS (
  SELECT
    s.product_id,
    s.sku_code,
    s.canonical_code,
    s.price_status,
    in_use.safe_num(o->>'price')::numeric AS price,
    o->>'price_list' AS price_list,
    o->>'source_pdf' AS source_pdf,
    in_use.safe_num(o->>'source_page')::int AS source_page,
    o->>'effective_date' AS effective_date,
    o->>'price_status' AS observation_status,
    o->>'context' AS context,
    o->>'column' AS price_column,
    in_use.norm_code(split_part(o->>'context', '|', 1)) AS context_head
  FROM in_use.mv_sku s
  CROSS JOIN LATERAL jsonb_array_elements(
    CASE
      WHEN jsonb_typeof(s.price_observations) = 'array' THEN s.price_observations
      ELSE '[]'::jsonb
    END
  ) AS o
)
SELECT
  ob.product_id,
  ob.sku_code,
  ob.canonical_code,
  ob.price_status,
  ob.price,
  ob.price_list,
  ob.source_pdf,
  ob.source_page,
  ob.effective_date,
  ob.observation_status,
  ob.context,
  ob.price_column,
  (
    ob.context ILIKE '%' || ob.sku_code || '%'
    OR ob.context ILIKE '%' || ob.canonical_code || '%'
  ) AS context_names_own_code,
  CASE
    WHEN ob.context_head <> '' AND NOT COALESCE(head.names_self, false)
    THEN head.other_code
  END AS context_sibling_code
FROM observation ob
LEFT JOIN LATERAL (
  SELECT
    bool_or(a.product_id = ob.product_id) AS names_self,
    min(a.code) FILTER (WHERE a.product_id <> ob.product_id) AS other_code
  FROM in_use.mv_code_alias a
  WHERE in_use.norm_code(a.code) = ob.context_head
) AS head ON true;

CREATE INDEX mv_price_product_id_idx ON in_use.mv_price (product_id);
CREATE INDEX mv_price_sku_code_idx ON in_use.mv_price (sku_code);

CREATE MATERIALIZED VIEW in_use.mv_source AS
SELECT
  s.product_id,
  CASE
    WHEN src LIKE 'Brochure:%' THEN 'brochure_md'
    WHEN src LIKE 'Product page:%' THEN 'product_page'
    WHEN src ~ '\.pdf p[0-9]+$' THEN 'pricelist_pdf'
    ELSE 'other'
  END AS ref_type,
  CASE
    WHEN src LIKE 'Brochure:%'
      THEN regexp_replace(src, '^Brochure:\s*([^ ]+).*$', '\1')
    WHEN src ~ '\.pdf p[0-9]+$'
      THEN regexp_replace(src, '^(.*\.pdf) p[0-9]+$', '\1')
    WHEN src LIKE 'Product page:%'
      THEN regexp_replace(src, '^Product page:\s*', '')
    ELSE src
  END AS ref_name,
  CASE WHEN src ~ '\.pdf p[0-9]+$'
       THEN regexp_replace(src, '^.*\.pdf p([0-9]+)$', '\1')::int END AS page
FROM in_use.mv_sku s
CROSS JOIN LATERAL jsonb_array_elements_text(
  CASE
    WHEN jsonb_typeof(s.sources) = 'array' THEN s.sources
    ELSE '[]'::jsonb
  END
) AS source(src);

CREATE INDEX mv_source_product_id_idx ON in_use.mv_source (product_id);
CREATE INDEX mv_source_type_idx ON in_use.mv_source (ref_type);

CREATE MATERIALIZED VIEW in_use.mv_spec_registry AS
SELECT
  family,
  spec_id,
  mode() WITHIN GROUP (ORDER BY spec_label) AS spec_label,
  mode() WITHIN GROUP (ORDER BY unit) AS unit,
  mode() WITHIN GROUP (ORDER BY value_kind) AS value_kind,
  bool_or(is_canonical_spec) AS is_canonical_spec,
  count(DISTINCT product_id) AS sku_count,
  count(*) FILTER (WHERE value_kind = 'composite') AS composite_count,
  min(COALESCE(value_min, value_num)) AS observed_min,
  max(COALESCE(value_max, value_num)) AS observed_max
FROM in_use.mv_fact
GROUP BY family, spec_id;

CREATE UNIQUE INDEX mv_spec_registry_family_spec_idx
  ON in_use.mv_spec_registry (family, spec_id);

CREATE MATERIALIZED VIEW in_use.mv_facet AS
SELECT
  s.family,
  d.key AS axis,
  COALESCE(
    d.value->>'meaning',
    d.value->>'code',
    trim(BOTH '"' FROM d.value::text)
  ) AS meaning,
  d.value->>'code' AS code,
  count(*) AS sku_count
FROM in_use.mv_sku s
CROSS JOIN LATERAL jsonb_each(
  CASE WHEN jsonb_typeof(s.decoded) = 'object' THEN s.decoded ELSE '{}'::jsonb END
) AS d
GROUP BY 1, 2, 3, 4;

CREATE INDEX mv_facet_family_axis_idx ON in_use.mv_facet (family, axis);

CREATE MATERIALIZED VIEW in_use.mv_chunk_index AS
SELECT
  product_id,
  product->>'sku_code' AS sku_code,
  chunk_type,
  id AS chunk_id,
  taxonomy->'headings' AS headings,
  length(content) AS content_len
FROM in_use.product_chunks
WHERE is_active;

CREATE INDEX mv_chunk_index_product_type_idx
  ON in_use.mv_chunk_index (product_id, chunk_type);
CREATE INDEX mv_chunk_index_type_idx ON in_use.mv_chunk_index (chunk_type);
