"""Compile role-specific instances of the private specialist graph."""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from cs_agent.tools.registry import tools_for_agent

from .nodes import (
    SpecialistState,
    after_record,
    make_agent_node,
    make_report_node,
    prepare,
    record,
    should_use_tools,
)
from .tool_node import make_tool_node


@lru_cache(maxsize=5)
def build_specialist_graph(agent_name: str):
    tools = tools_for_agent(agent_name)
    graph = StateGraph(SpecialistState)
    graph.add_node("prepare", prepare)
    graph.add_node("agent", make_agent_node(agent_name, tools))
    graph.add_node("tools", make_tool_node(tools))
    graph.add_node("record", record)
    graph.add_node("report", make_report_node(agent_name, tools))
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "agent")
    graph.add_conditional_edges("agent", should_use_tools)
    graph.add_edge("tools", "record")
    graph.add_conditional_edges("record", after_record)
    graph.add_edge("report", END)
    return graph.compile()
