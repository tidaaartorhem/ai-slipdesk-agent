"""SlipDesk findings: headline numbers for the README and the UI."""
from __future__ import annotations

from .data import load_corpus, load_queue


def findings() -> dict:
    queue = load_queue()
    corpus = load_corpus()
    sellers = queue["sellers"]
    by_route: dict[str, int] = dict(queue["segments"])
    escalate = [s for s in sellers if s["route"] == "ESCALATE"]
    reset = [s for s in sellers if s.get("reset_lead_time")]
    overdue = sum(s.get("overdue_open", 0) for s in sellers)
    return {
        "window": queue["window"],
        "snapshot": queue["snapshot_date"],
        "queue_size": len(sellers),
        "scored_sellers": queue["scored_sellers"],
        "total_sellers_window": queue["total_sellers_window"],
        "delivered_orders": queue["delivered_orders"],
        "late_orders": queue["late_orders"],
        "late_rate": queue["late_rate"],
        "by_route": by_route,
        "escalate": [
            {
                "seller_id": s["seller_id"],
                "orders": s["orders"],
                "late_rate": s["late_rate"],
                "score": s["score"],
            }
            for s in escalate
        ],
        "reset_lead_time_count": len(reset),
        "overdue_open_in_queue": overdue,
        "overdue_open_corpus": corpus["overdue_open"],
        "corpus": corpus,
    }
