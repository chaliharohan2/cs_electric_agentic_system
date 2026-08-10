"""LangChain structured-tool registry."""

from langchain_core.tools import StructuredTool

from cs_agent.subgraphs.analytics.tool import analytics_query

from . import descriptions
from .impl import (
    get_product,
    list_categories,
    list_facts,
    product_search,
    search_documents,
)
from .schemas import (
    AnalyticsQueryInput,
    GetProductInput,
    ListCategoriesInput,
    ListFactsInput,
    ProductSearchInput,
    SearchDocumentsInput,
)

TOOLS = [
    StructuredTool.from_function(
        func=list_categories,
        name="list_categories",
        description=descriptions.LIST_CATEGORIES,
        args_schema=ListCategoriesInput,
    ),
    StructuredTool.from_function(
        func=list_facts,
        name="list_facts",
        description=descriptions.LIST_FACTS,
        args_schema=ListFactsInput,
    ),
    StructuredTool.from_function(
        func=product_search,
        name="product_search",
        description=descriptions.PRODUCT_SEARCH,
        args_schema=ProductSearchInput,
    ),
    StructuredTool.from_function(
        func=get_product,
        name="get_product",
        description=descriptions.GET_PRODUCT,
        args_schema=GetProductInput,
    ),
    StructuredTool.from_function(
        func=search_documents,
        name="search_documents",
        description=descriptions.SEARCH_DOCUMENTS,
        args_schema=SearchDocumentsInput,
    ),
    StructuredTool.from_function(
        func=analytics_query,
        name="analytics_query",
        description=descriptions.ANALYTICS_QUERY,
        args_schema=AnalyticsQueryInput,
    ),
]

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
