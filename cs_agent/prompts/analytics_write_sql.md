Write ONE PostgreSQL SELECT statement answering the question below.

Schema:
{schema_ddl}

Canonical facts in scope:
{fact_registry}

Rules:
- One statement, SELECT only.
- Facts that carry conditions must be filtered on those conditions, or the comparison
  is meaningless.
- Handle NULLs explicitly when ranking; a missing fact is not a zero.
- Return the columns requested in output_shape, using those names.

Output only the SQL. No explanation, no fences.
