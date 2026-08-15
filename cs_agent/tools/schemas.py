"""Pydantic args schemas for catalogue tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SpecFilter(BaseModel):
    spec_id: str
    op: Literal["gte", "lte", "eq", "contains"]
    value: float | str


def _as_str_list(value: Any) -> list[str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


class ProductSearchArgs(BaseModel):
    path: list[str] | None = None
    family: str | None = None
    facets: dict[str, str] | None = None
    filters: list[SpecFilter] = Field(default_factory=list)
    market_segment: str | None = None
    price_status: list[str] | None = Field(
        None,
        description='Filter by price_status values, e.g. ["listed"]. A single string is accepted.',
    )
    has_chunk_type: list[str] | None = None
    text: str | None = Field(None, description="Optional free-text name/code match.")
    return_specs: list[str] = Field(default_factory=list)
    limit: int = Field(20, ge=1, le=100)

    @field_validator("price_status", "has_chunk_type", mode="before")
    @classmethod
    def _coerce_str_list(cls, value: Any) -> list[str] | None:
        return _as_str_list(value)

    @field_validator("limit", mode="before")
    @classmethod
    def _clamp_limit(cls, value: Any) -> int:
        try:
            return max(1, min(int(value), 100))
        except (TypeError, ValueError):
            return 20


class GetSkuArgs(BaseModel):
    sku_code: str
    include: list[
        Literal["facts", "decoded", "chunks", "sources", "price", "peers"]
    ] = Field(
        default_factory=lambda: ["facts", "decoded", "sources"]
    )
    chunk_types: list[str] | None = None


class CompareSkusArgs(BaseModel):
    sku_codes: list[str] = Field(min_length=2, max_length=10)
    spec_ids: list[str] | None = None


class SearchDocumentsArgs(BaseModel):
    query: str
    path: list[str] | None = None
    family: str | None = None
    sku_code: str | None = None
    chunk_types: list[str] | None = None
    k: int = Field(6, ge=1, le=20)


class TaxonomyBrowseArgs(BaseModel):
    path: list[str] | None = None
    market_segment: str | None = None
    include_facets: bool = False


class ListCanonicalSpecsArgs(BaseModel):
    family: str | None = None
    spec_id_contains: str | None = None
    canonical_only: bool = False


class ResolveProductArgs(BaseModel):
    query: str
    family_hint: str | None = None
    limit: int = Field(8, ge=1, le=20)


class GetPriceDetailArgs(BaseModel):
    sku_codes: list[str] = Field(min_length=1, max_length=10)


class GetPeerGroupArgs(BaseModel):
    sku_code: str


class AnalyticsQueryArgs(BaseModel):
    question: str
    output_shape: str = Field(
        ...,
        description=(
            "Requested focus and organization of the final factual summary, "
            "including any desired groups, metrics, or comparison grain."
        ),
    )
