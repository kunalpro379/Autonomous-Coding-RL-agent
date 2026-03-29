from __future__ import annotations

from langgraph.graph import END, StateGraph

from agents.developer import developer_node
from agents.executor import executor_node
from agents.evaluator import evaluator_node
from agents.planner import planner_node
from agents.retriever import retriever_node
from agents.rl_agent import rl_node
from agents.tester import tester_node
from config.settings import settings
from memory.checkpointer import get_checkpointer
from states.graph_state import AgentState


def route_after_rl(state: AgentState) -> str:
    retries = int(state.get("retry_count") or 0)
    hard_max = int(getattr(settings, "hard_max_retries", 8))
    # Hard safety guard to avoid infinite loops.
    if retries >= hard_max:
        return "end"
    decision = (state.get("rl_decision") or "STOP").upper()
    if decision == "STOP":
        return "end"
    if decision == "REPLAN":
        return "replan"
    return "rewrite"


def bump_retry(state: AgentState) -> AgentState:
    return {"retry_count": int(state.get("retry_count") or 0) + 1}


def continue_after_bump(state: AgentState) -> str:
    retries = int(state.get("retry_count") or 0)
    hard_max = int(getattr(settings, "hard_max_retries", 8))
    if retries >= hard_max:
        return "end"
    # We stash next hop in meta to avoid ambiguous edges
    nxt = (state.get("meta") or {}).get("rl_next", "developer")
    return "planner" if nxt == "planner" else "developer"


def mark_next_and_bump(state: AgentState) -> AgentState:
    decision = (state.get("rl_decision") or "STOP").upper()
    nxt = "planner" if decision == "REPLAN" else "developer"
    meta = dict(state.get("meta") or {})
    meta["rl_next"] = nxt
    # Reset inner dev loop counter on each outer RL cycle transition.
    meta["dev_loop_count"] = 0
    return {"retry_count": int(state.get("retry_count") or 0) + 1, "meta": meta}


def bump_dev_loop(state: AgentState) -> AgentState:
    meta = dict(state.get("meta") or {})
    meta["dev_loop_count"] = int(meta.get("dev_loop_count") or 0) + 1
    return {"meta": meta}


def route_after_tester(state: AgentState) -> str:
    meta = state.get("meta") or {}
    last_exit = int(meta.get("last_exit_code", 1))
    has_executor_error = bool(meta.get("executor_error"))
    dev_loop_count = int(meta.get("dev_loop_count") or 0)
    max_dev = int(getattr(settings, "max_dev_loops_per_cycle", 4))

    # Keep developer/executor/tester loop local until pass or loop budget exhausted.
    if (last_exit == 0) and (not has_executor_error):
        return "evaluate"
    if dev_loop_count >= max_dev:
        return "evaluate"
    return "rewrite"


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("planner", planner_node)
    g.add_node("retriever", retriever_node)
    g.add_node("developer", developer_node)
    g.add_node("executor", executor_node)
    g.add_node("tester", tester_node)
    g.add_node("dev_bump", bump_dev_loop)
    g.add_node("evaluator", evaluator_node)
    g.add_node("rl_agent", rl_node)
    g.add_node("bump", mark_next_and_bump)
    g.add_node("post_bump_router", lambda s: {})

    g.set_entry_point("planner")
    g.add_edge("planner", "retriever")
    g.add_edge("retriever", "developer")
    g.add_edge("developer", "executor")
    g.add_edge("executor", "tester")
    g.add_conditional_edges(
        "tester",
        route_after_tester,
        {"evaluate": "evaluator", "rewrite": "dev_bump"},
    )
    g.add_edge("dev_bump", "developer")
    g.add_edge("evaluator", "rl_agent")

    g.add_conditional_edges(
        "rl_agent",
        route_after_rl,
        {"end": END, "replan": "bump", "rewrite": "bump"},
    )

    # post_bump_router is a no-op node solely to branch
    g.add_edge("bump", "post_bump_router")
    g.add_conditional_edges(
        "post_bump_router",
        continue_after_bump,
        {"end": END, "planner": "planner", "developer": "developer"},
    )

    return g.compile(checkpointer=get_checkpointer())