"""LangChain structured-tool registry."""

from langchain_core.tools import StructuredTool

from cs_agent.subgraphs.analytics.tool import analytics_query

from . import descriptions
from .impl import (
    catalogue_map,
    compare_skus,
    get_peer_group,
    get_price_detail,
    get_sku,
    list_canonical_specs,
    product_search,
    resolve_product,
    search_documents,
    taxonomy_browse,
)
from .schemas import (
    AnalyticsQueryArgs,
    CatalogueMapArgs,
    CompareSkusArgs,
    GetPeerGroupArgs,
    GetPriceDetailArgs,
    GetSkuArgs,
    ListCanonicalSpecsArgs,
    ProductSearchArgs,
    ResolveProductArgs,
    SearchDocumentsArgs,
    TaxonomyBrowseArgs,
)

TOOLS = [
    StructuredTool.from_function(
        func=resolve_product,
        name="resolve_product",
        description=descriptions.RESOLVE_PRODUCT,
        args_schema=ResolveProductArgs,
    ),
    StructuredTool.from_function(
        func=list_canonical_specs,
        name="list_canonical_specs",
        description=descriptions.LIST_CANONICAL_SPECS,
        args_schema=ListCanonicalSpecsArgs,
    ),
    StructuredTool.from_function(
        func=catalogue_map,
        name="catalogue_map",
        description=descriptions.CATALOGUE_MAP,
        args_schema=CatalogueMapArgs,
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
        func=get_price_detail,
        name="get_price_detail",
        description=descriptions.GET_PRICE_DETAIL,
        args_schema=GetPriceDetailArgs,
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
        func=get_peer_group,
        name="get_peer_group",
        description=descriptions.GET_PEER_GROUP,
        args_schema=GetPeerGroupArgs,
    ),
    StructuredTool.from_function(
        func=analytics_query,
        name="analytics_query",
        description=descriptions.ANALYTICS_QUERY,
        args_schema=AnalyticsQueryArgs,
    ),
]

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}

SHARED_TOOL_NAMES = ("resolve_product", "product_search", "get_sku")
AGENT_TOOL_NAMES = {
    "discovery": (
        "catalogue_map",
        "taxonomy_browse",
        "list_canonical_specs",
        "search_documents",
        "get_price_detail",
        "get_peer_group",
    ),
    "spec_selection": (
        "catalogue_map",
        "taxonomy_browse",
        "list_canonical_specs",
        "search_documents",
        "get_price_detail",
        "compare_skus",
        "get_peer_group",
        "analytics_query",
    ),
    "solution_advisory": (
        "catalogue_map",
        "taxonomy_browse",
        "list_canonical_specs",
        "search_documents",
        "get_price_detail",
    ),
    "comparison": (
        "catalogue_map",
        "taxonomy_browse",
        "list_canonical_specs",
        "search_documents",
        "get_price_detail",
        "compare_skus",
        "get_peer_group",
        "analytics_query",
    ),
    "compliance": (
        "catalogue_map",
        "taxonomy_browse",
        "list_canonical_specs",
        "search_documents",
    ),
}

SHARED_TOOLS = [TOOLS_BY_NAME[name] for name in SHARED_TOOL_NAMES]
AGENT_TOOLS = {
    agent: [TOOLS_BY_NAME[name] for name in names]
    for agent, names in AGENT_TOOL_NAMES.items()
}


def tools_for_agent(agent: str):
    return [*SHARED_TOOLS, *AGENT_TOOLS[agent]]
