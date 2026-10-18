"""LangGraph wrapper for the agent view.

The pipeline's logic lives in plain Python (helm.pipeline), so it is testable without LangGraph.
This module declares the same topology as a LangGraph StateGraph so the Agents screen can draw it
and replay what a run did through the graph (including the ALLOW / ESCALATE branch).
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

ORDER = ["reader", "forecaster", "collections", "scheduler", "treasury", "policy"]


class RunState(TypedDict, total=False):
    escalated: bool
    visited: list[str]


def _node(name: str):
    def run(state: RunState) -> RunState:
        return {"visited": [*state.get("visited", []), name]}
    run.__name__ = name
    return run


def build_graph():
    g = StateGraph(RunState)
    for n in [*ORDER, "human", "executor", "explainer", "watchdog"]:
        g.add_node(n, _node(n))
    g.add_edge(START, "reader")
    for a, b in zip(ORDER, ORDER[1:]):
        g.add_edge(a, b)
    # Only ESCALATE decisions detour through the owner; ALLOW goes straight to the Executor.
    g.add_conditional_edges("policy", lambda s: "human" if s.get("escalated") else "executor", {"human": "human", "executor": "executor"})
    g.add_edge("human", "executor")
    g.add_edge("executor", "explainer")
    g.add_edge("explainer", "watchdog")
    g.add_edge("watchdog", END)
    return g.compile()


def replay(escalated: bool) -> list[str]:
    return build_graph().invoke({"escalated": escalated, "visited": []})["visited"]


def mermaid() -> str:
    return build_graph().get_graph().draw_mermaid()
