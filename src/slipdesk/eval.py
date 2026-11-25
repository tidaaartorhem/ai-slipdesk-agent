"""Golden-set evaluation for SlipDesk.

Each golden entry is a seller whose numbers were verified against the
raw Olist rows (or a hand-computed edge case). The eval asserts the
engine reproduces the expected route — and, for the hand-computed
cases, the exact score.
"""
from __future__ import annotations

from .data import load_golden
from .scoring import route_seller, score_seller


def evaluate() -> dict:
    golden = load_golden()
    results = []
    for entry in golden["entries"]:
        score, parts = score_seller(entry["stats"])
        route = route_seller(score, entry["stats"]["n"])
        expected_route = entry["expected_route"]
        expected_score = entry.get("expected_score")
        ok = route == expected_route and (
            expected_score is None or abs(score - expected_score) < 0.05
        )
        results.append(
            {
                "seller_id": entry["seller_id"],
                "score": score,
                "expected_score": expected_score,
                "route": route,
                "expected_route": expected_route,
                "pass": ok,
            }
        )
    passed = sum(1 for r in results if r["pass"])
    return {
        "total": len(results),
        "passed": passed,
        "accuracy": round(passed / len(results), 4) if results else 0.0,
        "results": results,
    }
