"""LangChain structured-tool registry."""

from langchain_core.tools import StructuredTool

from cs_agent.subgraphs.analytics.tool import analytics_query

from . import descriptions
from .impl import (
    compare_skus,
    get_sku,
    list_canonical_specs,
    product_search,
    search_documents,
    taxonomy_browse,
)
from .schemas import (
    AnalyticsQueryArgs,
    CompareSkusArgs,
    GetSkuArgs,
    ListCanonicalSpecsArgs,
    ProductSearchArgs,
    SearchDocumentsArgs,
    TaxonomyBrowseArgs,
)

TOOLS = [
    StructuredTool.from_function(
        func=list_canonical_specs,
        name="list_canonical_specs",
        description=descriptions.LIST_CANONICAL_SPECS,
        args_schema=ListCanonicalSpecsArgs,
    ),
    StructuredTool.from_function(
        func=taxonomy_browse,
        name="taxonomy_browse",
        description=descriptions.TAXONOMY_BROWSE,
        args_schema=TaxonomyBrowseArgs,
    ),
    StructuredTool.from_function(
        func=product_search,
        name="product_search",
        description=descriptions.PRODUCT_SEARCH,
        args_schema=ProductSearchArgs,
    ),
    StructuredTool.from_function(
        func=get_sku,
        name="get_sku",
        description=descriptions.GET_SKU,
        args_schema=GetSkuArgs,
    ),
    StructuredTool.from_function(
        func=compare_skus,
        name="compare_skus",
        description=descriptions.COMPARE_SKUS,
        args_schema=CompareSkusArgs,
    ),
    StructuredTool.from_function(
        func=search_documents,
        name="search_documents",
        description=descriptions.SEARCH_DOCUMENTS,
        args_schema=SearchDocumentsArgs,
    ),
    StructuredTool.from_function(
        func=analytics_query,
        name="analytics_query",
        description=descriptions.ANALYTICS_QUERY,
        args_schema=AnalyticsQueryArgs,
    ),
]

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
