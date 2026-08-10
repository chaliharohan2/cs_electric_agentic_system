"""Analytics subgraph construction."""

from langgraph.graph import END, START, StateGraph

from .nodes import AnalyticsState, execute_sql, shape, write_sql


def build_analytics_graph():
    graph = StateGraph(AnalyticsState)
    graph.add_node("write_sql", write_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("shape", shape)
    graph.add_edge(START, "write_sql")
    graph.add_edge("write_sql", "execute_sql")
    graph.add_edge("execute_sql", "shape")
    graph.add_edge("shape", END)
    return graph.compile()
