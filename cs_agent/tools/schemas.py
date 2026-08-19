"""Pydantic args schemas for catalogue tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from cs_agent.backends.grouped_search import GROUP_BY_SCOPE_ERROR, GROUP_BY_VALUES


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


def _coerce_family(value: Any) -> str | list[str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    items = [str(item) for item in value if str(item).strip()]
    return items or None


class ProductSearchArgs(BaseModel):
    path: list[str] | None = None
    family: str | list[str] | None = None
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
    group_by: Literal[
        "family", "division", "product_group", "product_subgroup", "product_range"
    ] | None = None

    @field_validator("family", mode="before")
    @classmethod
    def _family(cls, value: Any) -> str | list[str] | None:
        return _coerce_family(value)

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

    @field_validator("group_by", mode="before")
    @classmethod
    def _empty_group_by(cls, value: Any) -> Any:
        if value == "":
            return None
        return value

    @model_validator(mode="after")
    def _group_by_needs_scope(self) -> "ProductSearchArgs":
        if self.group_by and self.group_by not in GROUP_BY_VALUES:
            raise ValueError(
                f"group_by must be one of {list(GROUP_BY_VALUES)}, not {self.group_by!r}."
            )
        if self.group_by and not self.family and not self.path:
            raise ValueError(GROUP_BY_SCOPE_ERROR)
        return self


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


class CatalogueMapArgs(BaseModel):
    path_text: str | None = None
    market_segment: str | None = None
    include_uncategorised: bool = True
    limit: int = Field(40, ge=1, le=100)

    @model_validator(mode="after")
    def _require_a_filter(self) -> "CatalogueMapArgs":
        """Refuse a call with neither filter.

        Unfiltered, this would dump the whole taxonomy, which `taxonomy_browse`
        already does one level at a time and more usefully. Raising here turns
        the mistake into a tool result naming the fix rather than a wasted call
        the model has to interpret from an oversized payload.
        """
        if not (self.path_text or "").strip() and not (
            self.market_segment or ""
        ).strip():
            raise ValueError(
                "catalogue_map needs path_text, market_segment, or both. Pass "
                "path_text for a product or category name ('wintrip', 'air "
                "circuit breaker'), market_segment for an audience "
                "('Residential'). To list the divisions instead, call "
                "taxonomy_browse with path=[]."
            )
        return self


class TaxonomyBrowseArgs(BaseModel):
    path: list[str] | None = None
    market_segment: str | None = None
    include_facets: bool = False


class ListCanonicalSpecsArgs(BaseModel):
    path: list[str] | None = None
    family: str | list[str] | None = None
    spec_id_contains: str | None = None
    canonical_only: bool = False

    @field_validator("family", mode="before")
    @classmethod
    def _family(cls, value: Any) -> str | list[str] | None:
        return _coerce_family(value)


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
    family: str | None = Field(
        default=None,
        description=(
            "Family or product-line name the analysis stays inside, matched as "
            "a substring. Supply it whenever the question is about one area: it "
            "narrows the specification vocabulary given to the SQL writer from "
            "the whole catalogue to that family, which makes the query more "
            "accurate. Omit only for genuinely catalogue-wide questions."
        ),
    )
