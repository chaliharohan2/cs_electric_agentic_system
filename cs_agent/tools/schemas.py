"""Pydantic args schemas for catalogue tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FactFilter(BaseModel):
    canonical_fact_id: str
    op: Literal["eq", "gte", "lte", "in", "contains"] = "eq"
    value: Any
    conditions: dict | None = Field(
        None,
        description=(
            'e.g. {"voltage_v": 415, "poles": 3}. Required when the fact '
            "declares condition_keys."
        ),
    )


class ProductSearchArgs(BaseModel):
    category_path: str
    filters: list[FactFilter] = []
    text: str | None = Field(None, description="Optional free-text name/code match.")
    limit: int = 20


class GetProductArgs(BaseModel):
    family_id: str
    fact_groups: list[
        Literal[
            "electrical",
            "mechanical",
            "dimensions",
            "certifications",
            "trip_units",
            "accessories",
            "commercial",
        ]
    ]
    include_variants: bool = False


class SearchDocumentsArgs(BaseModel):
    query: str
    category_path: str | None = None
    family_id: str | None = None
    k: int = 6


class TaxonomyBrowseArgs(BaseModel):
    node_id: str | None = Field(None, description="Category node. Omit for the root.")
    depth: int = Field(1, description="Levels to expand, 1-2.")


class ListCanonicalFactsArgs(BaseModel):
    category_path: str | None = Field(
        None,
        description="Taxonomy path, e.g. 'protection/mccb'. Omit for all categories.",
    )


class AnalyticsQueryArgs(BaseModel):
    question: str
    scope: dict | None = Field(
        None,
        description="family_ids[] or a category_path to bound the query.",
    )
    output_shape: str = Field(
        ...,
        description="e.g. 'one row per family, columns: code, In, Icu@415V, price'",
    )
