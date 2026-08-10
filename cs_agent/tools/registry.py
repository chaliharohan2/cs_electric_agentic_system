"""LangChain structured-tool registry."""

from langchain_core.tools import StructuredTool

from cs_agent.subgraphs.analytics.tool import analytics_query

from . import descriptions
from .impl import (
    get_product,
    list_canonical_facts,
    product_search,
    search_documents,
    taxonomy_browse,
)
from .schemas import (
    AnalyticsQueryArgs,
    GetProductArgs,
    ListCanonicalFactsArgs,
    ProductSearchArgs,
    SearchDocumentsArgs,
    TaxonomyBrowseArgs,
)

TOOLS = [
    StructuredTool.from_function(
        func=list_canonical_facts,
        name="list_canonical_facts",
        description=descriptions.LIST_CANONICAL_FACTS,
        args_schema=ListCanonicalFactsArgs,
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
        func=get_product,
        name="get_product",
        description=descriptions.GET_PRODUCT,
        args_schema=GetProductArgs,
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
