"""Pydantic input contracts for catalogue tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ListCategoriesInput(BaseModel):
    pass


class ListFactsInput(BaseModel):
    category: str = Field(description="Exact taxonomy category identifier.")


class FactFilter(BaseModel):
    canonical_fact_id: str
    operator: Literal["eq", "gte", "lte", "contains"] = "eq"
    value_num: float | None = None
    value_text: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def exactly_one_value(self) -> "FactFilter":
        if (self.value_num is None) == (self.value_text is None):
            raise ValueError("Provide exactly one of value_num or value_text")
        return self


class ProductSearchInput(BaseModel):
    category: str
    filters: list[FactFilter] = Field(default_factory=list)


class GetProductInput(BaseModel):
    family_id: str


class SearchDocumentsInput(BaseModel):
    query: str
    family_id: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


class AnalyticsQueryInput(BaseModel):
    question: str = Field(description="Natural-language analytical question.")
