"""SlipDesk LangGraph pipeline.

StateGraph: intake -> measure -> score -> segment -> draft -> gate

- intake:   load the Q3 2017 seller queue + scoring config.
- measure:  per-seller aggregates are already computed by the fetch
            script (slip days, late rate, breach rate, trend split,
            p90 transit); this node re-derives the score inputs from
            the stored aggregates so the graph owns the math.
- score:    0-100 slip-risk score with disclosed parts.
- segment:  ESCALATE / AT_RISK / WATCH / RELIABLE (or UNSCORED).
- draft:    one recommended action per seller + a human-gated chase
            draft (nothing is sent).
- gate:     export pack; every action is a draft pending human approval.
"""
from __future__ import annotations

from typing import Any

from .data import load_config, load_queue
from .scoring import chase_draft, recommended_action, route_seller, score_seller


def node_intake(state: dict) -> dict:
    queue = load_queue()
    return {
        **state,
        "sellers": queue["sellers"],
        "queue_meta": {k: v for k, v in queue.items() if k != "sellers"},
        "config": load_config(),
    }


def node_measure(state: dict) -> dict:
    measured = []
    for s in state["sellers"]:
        measured.append(
            {
                **s,
                "late_rate": round(s["late_orders"] / s["orders"], 4) if s["orders"] else 0.0,
                "breach_rate": round(s["breach_orders"] / s["orders"], 4) if s["orders"] else 0.0,
            }
        )
    return {**state, "sellers": measured}


def node_score(state: dict) -> dict:
    scored = []
    for s in state["sellers"]:
        score, parts = score_seller(s)
        scored.append({**s, "score": score, "score_parts": parts})
    return {**state, "sellers": scored}


def node_segment(state: dict) -> dict:
    segmented = []
    for s in state["sellers"]:
        segmented.append({**s, "route": route_seller(s["score"], s["orders"])})
    return {**state, "sellers": segmented}


def node_draft(state: dict) -> dict:
    drafted = []
    for s in state["sellers"]:
        action, instruction = recommended_action(s)
        drafted.append(
            {**s, "action": action, "instruction": instruction, "draft": chase_draft(s)}
        )
    return {**state, "sellers": drafted}


def node_gate(state: dict) -> dict:
    pack = []
    for s in state["sellers"]:
        pack.append(
            {
                "seller_id": s["seller_id"],
                "seller_state": s["seller_state"],
                "seller_city": s["seller_city"],
                "orders": s["orders"],
                "late_orders": s["late_orders"],
                "late_rate": s["late_rate"],
                "median_slip": s["median_slip"],
                "late_median_slip": s["late_median_slip"],
                "max_slip": s["max_slip"],
                "worst_order_id": s["worst_order_id"],
                "breach_orders": s["breach_orders"],
                "breach_rate": s["breach_rate"],
                "sep_late_rate": s["sep_late_rate"],
                "sep_n": s["sep_n"],
                "ja_late_rate": s["ja_late_rate"],
                "ja_n": s["ja_n"],
                "promised_median_days": s["promised_median_days"],
                "p90_transit_days": s["p90_transit_days"],
                "recommended_promise_days": s["recommended_promise_days"],
                "reset_lead_time": s["reset_lead_time"],
                "overdue_open": s["overdue_open"],
                "score": s["score"],
                "score_parts": s["score_parts"],
                "route": s["route"],
                "action": s["action"],
                "instruction": s["instruction"],
                "draft": s["draft"],
                "pending_approval": True,
            }
        )
    return {**state, "export_pack": pack}


NODES = [node_intake, node_measure, node_score, node_segment, node_draft, node_gate]


def build_graph():
    """Return a compiled LangGraph StateGraph; fall back to a sequential
    runner when langgraph is not installed (same node order, same state)."""
    try:
        from langgraph.graph import StateGraph  # type: ignore

        g: Any = StateGraph(dict)
        prev = None
        for fn in NODES:
            name = fn.__name__.replace("node_", "")
            g.add_node(name, fn)
            if prev:
                g.add_edge(prev, name)
            else:
                g.set_entry_point(name)
            prev = name
        g.add_edge(prev, "__end__")
        return g.compile()
    except ImportError:
        return None


def run() -> dict:
    graph = build_graph()
    if graph is not None:
        return graph.invoke({})
    state: dict = {}
    for fn in NODES:
        state = fn(state)
    return state
