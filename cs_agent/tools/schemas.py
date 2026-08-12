"""Pydantic args schemas for catalogue tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SpecFilter(BaseModel):
    spec_id: str
    op: Literal["gte", "lte", "eq", "contains"]
    value: float | str


class ProductSearchArgs(BaseModel):
    category: str | None = None
    family: str | None = None
    facets: dict[str, str] | None = None
    filters: list[SpecFilter] = Field(default_factory=list)
    text: str | None = Field(None, description="Optional free-text name/code match.")
    return_specs: list[str] = Field(default_factory=list)
    limit: int = Field(20, ge=1, le=100)


class GetSkuArgs(BaseModel):
    sku_code: str
    include: list[Literal["facts", "decoded", "content", "sources"]] = Field(
        default_factory=lambda: ["facts", "decoded"]
    )


class CompareSkusArgs(BaseModel):
    sku_codes: list[str] = Field(min_length=2, max_length=10)
    spec_ids: list[str] | None = None


class SearchDocumentsArgs(BaseModel):
    query: str
    category: str | None = None
    family: str | None = None
    sku_code: str | None = None
    k: int = Field(6, ge=1, le=20)


class TaxonomyBrowseArgs(BaseModel):
    category: str | None = None
    family: str | None = None


class ListCanonicalSpecsArgs(BaseModel):
    category: str | None = None


class AnalyticsQueryArgs(BaseModel):
    question: str
    output_shape: str = Field(
        ...,
        description="Requested columns and row grain for the result table.",
    )
