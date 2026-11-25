#!/usr/bin/env python3
"""Fetch the Olist Brazilian E-Commerce dataset and build SlipDesk's
committed data (data/raw/*.json).

Source: Olist (Kaggle, CC BY 4.0), mirrored with zero auth at
https://github.com/olist/work-at-olist-data (datasets/ folder).
CSVs are cached in data/raw/ when a sibling checkout already has them
(ai-reconciliation-agent), otherwise downloaded from the mirror. The
CSVs themselves are NOT committed — only the derived queue, stats,
config, golden set, and test vectors are.

Replay: purchases 2017-07-01..2017-09-30 (Q3 2017), snapshot as of
2017-10-31. Unit of analysis: the seller. Scored sellers need >= 5
delivered orders in the window; the web queue is the top 100 by score.

Outputs:
  queue.json          — top 100 Q3 2017 sellers by slip-risk score
                        + window/corpus meta
  corpus_stats.json   — full-corpus slip counts (all 96,470 delivered
                        orders), monthly late rates, breach rate,
                        still-waiting overdue count
  scoring-config.json — disclosed thresholds + weights
  golden_set.json     — hand-verified sellers + hand-computed edge cases
  test-vectors.json   — shared Python/TS contract vectors
"""
from __future__ import annotations

import csv
import json
import math
import shutil
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
sys.path.insert(0, str(ROOT / "src"))

from slipdesk.scoring import (  # noqa: E402
    AT_RISK_SCORE,
    ESCALATE_SCORE,
    LEAD_RESET_GAP,
    MIN_ORDERS,
    SNAPSHOT_DATE,
    WATCH_SCORE,
    WINDOW_END,
    WINDOW_START,
    recommended_action,
    recommended_promise_days,
    route_seller,
    score_seller,
)

MIRROR = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/"
SIBLING_CACHE = Path("/home/hatch/workspace/github-repos/ai-reconciliation-agent/data/raw")
FILES = {
    "orders": "olist_orders_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
}
QUEUE_N = 100

# Sellers whose numbers were verified by hand against the analysis of the
# raw Olist rows (see README). expected_route is asserted by the eval; the
# script prints each one's inputs so the numbers stay eyeball-verifiable.
GOLDEN_SELLERS = [
    "633ecdf879b94b5337cca303328e4a25",  # 6 orders, 67% late, 83% breach
    "75d34ebb1bd0bd7dde40dd507b8169c3",  # 11 orders, 33% late, Sep 100% late
    "5011f0d93373a4c5753adf58ca77af8d",  # 6 orders, 33% late, median 28d late
    "835f0f7810c76831d6c7d24c7a646d4d",  # 18 orders, 29% late, 71% breach
    "53e4c6e0f4312d4d2107a8c9cddf45cd",  # 76 orders, one 109-day slip
    "1f50f920176fa81dab994f9023523100",  # 261 orders, 2.6% late, one 65-day slip
]


def _d(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def _days(a: date | None, b: date | None) -> int | None:
    if a is None or b is None:
        return None
    return (a - b).days


def fetch_csvs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for key, name in FILES.items():
        path = RAW / name
        if path.exists() and path.stat().st_size > 0:
            print(f"  {name}: cached ({path.stat().st_size // 1024} KB)")
            continue
        sibling = SIBLING_CACHE / name
        if sibling.exists() and sibling.stat().st_size > 0:
            shutil.copyfile(sibling, path)
            print(f"  {name}: copied from sibling checkout")
            continue
        url = MIRROR + name
        print(f"  {name}: downloading {url}")
        urllib.request.urlretrieve(url, path)
        print(f"  {name}: downloaded ({path.stat().st_size // 1024} KB)")


def main() -> None:
    fetch_csvs()

    sellers_meta: dict[str, dict] = {}
    with open(RAW / FILES["sellers"], newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sellers_meta[r["seller_id"]] = {
                "seller_city": r["seller_city"],
                "seller_state": r["seller_state"],
            }

    orders: dict[str, dict] = {}
    with open(RAW / FILES["orders"], newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            orders[r["order_id"]] = r

    items_by_order: dict[str, list[dict]] = defaultdict(list)
    with open(RAW / FILES["items"], newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            items_by_order[r["order_id"]].append(r)

    # ---- corpus stats (all delivered orders) ----
    corpus_slips = []
    corpus_breach_items = 0
    corpus_items_with_carrier = 0
    monthly: dict[str, list[int]] = defaultdict(list)
    for oid, o in orders.items():
        if o["order_status"] != "delivered":
            continue
        slip = _days(_d(o["order_delivered_customer_date"]), _d(o["order_estimated_delivery_date"]))
        if slip is None:
            continue
        corpus_slips.append(slip)
        ym = o["order_purchase_timestamp"][:7]
        monthly[ym].append(slip)
    for oid, items in items_by_order.items():
        o = orders.get(oid)
        if o is None:
            continue
        for it in items:
            ship_late = _days(_d(o["order_delivered_carrier_date"]), _d(it["shipping_limit_date"]))
            if ship_late is None:
                continue
            corpus_items_with_carrier += 1
            if ship_late > 0:
                corpus_breach_items += 1

    # ---- Q3 2017 window: per-seller aggregates ----
    win_start = date.fromisoformat(WINDOW_START)
    win_end = date.fromisoformat(WINDOW_END)
    snap = date.fromisoformat(SNAPSHOT_DATE)
    per_seller: dict[str, dict] = defaultdict(
        lambda: {
            "order_ids": set(),
            "slips": [],
            "late_order_ids": set(),
            "late_slips": [],
            "item_count": 0,
            "breach": 0,
            "sep": [],
            "ja": [],
            "sep_order_ids": set(),
            "ja_order_ids": set(),
            "transits": [],
            "promised": [],
            "max_slip": None,
            "worst_order_id": None,
        }
    )
    window_orders = 0
    window_late = 0
    for oid, o in orders.items():
        purchase = _d(o["order_purchase_timestamp"])
        if purchase is None or not (win_start <= purchase < win_end):
            continue
        if o["order_status"] != "delivered":
            continue
        slip = _days(_d(o["order_delivered_customer_date"]), _d(o["order_estimated_delivery_date"]))
        transit = _days(_d(o["order_delivered_customer_date"]), purchase)
        promised = _days(_d(o["order_estimated_delivery_date"]), purchase)
        if slip is None or transit is None or promised is None:
            continue
        window_orders += 1
        if slip > 0:
            window_late += 1
        month = o["order_purchase_timestamp"][:7]
        # One entry per seller-ORDER (not per item row): a 4-item order that
        # is late is one late order, not four. Breach is per item.
        sellers_in_order: dict[str, list[dict]] = defaultdict(list)
        for it in items_by_order.get(oid, []):
            sellers_in_order[it["seller_id"]].append(it)
        for sid, its in sellers_in_order.items():
            agg = per_seller[sid]
            agg["order_ids"].add(oid)
            agg["slips"].append(slip)
            if slip > 0:
                agg["late_order_ids"].add(oid)
                agg["late_slips"].append(slip)
            for it in its:
                agg["item_count"] += 1
                ship_late = _days(_d(o["order_delivered_carrier_date"]), _d(it["shipping_limit_date"]))
                if ship_late is not None and ship_late > 0:
                    agg["breach"] += 1
            (agg["sep"] if month == "2017-09" else agg["ja"]).append(slip)
            (agg["sep_order_ids"] if month == "2017-09" else agg["ja_order_ids"]).add(oid)
            agg["transits"].append(transit)
            agg["promised"].append(promised)
            if agg["max_slip"] is None or slip > agg["max_slip"]:
                agg["max_slip"] = slip
                agg["worst_order_id"] = oid

    # orders still open and past their promised date as of the snapshot
    overdue_by_seller: Counter = Counter()
    overdue_total = 0
    for oid, o in orders.items():
        purchase = _d(o["order_purchase_timestamp"])
        if purchase is None or not (win_start <= purchase < win_end):
            continue
        if o["order_status"] not in ("shipped", "invoiced", "processing", "approved", "created"):
            continue
        est = _d(o["order_estimated_delivery_date"])
        if est is None or est >= snap:
            continue
        overdue_total += 1
        for it in items_by_order.get(oid, []):
            overdue_by_seller[it["seller_id"]] += 1

    def median(xs: list[float]) -> float:
        xs = sorted(xs)
        n = len(xs)
        if n == 0:
            return 0.0
        return float(xs[n // 2]) if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

    def quantile(xs: list[float], q: float) -> float:
        xs = sorted(xs)
        if not xs:
            return 0.0
        idx = min(len(xs) - 1, max(0, math.ceil(q * len(xs)) - 1))
        return float(xs[idx])

    scored = []
    for sid, agg in per_seller.items():
        n = len(agg["order_ids"])
        if n < MIN_ORDERS:
            continue
        late_orders = len(agg["late_order_ids"])
        stats = {
            "n": n,
            "late_orders": late_orders,
            "late_rate": round(late_orders / n, 4),
            "late_median_slip": median(agg["late_slips"]),
            "max_slip": max(agg["slips"]),
            "breach_rate": round(agg["breach"] / agg["item_count"], 4) if agg["item_count"] else 0.0,
            "sep_late_rate": round(sum(1 for x in agg["sep"] if x > 0) / len(agg["sep"]), 4) if agg["sep"] else 0.0,
            "sep_n": len(agg["sep_order_ids"]),
            "ja_late_rate": round(sum(1 for x in agg["ja"] if x > 0) / len(agg["ja"]), 4) if agg["ja"] else 0.0,
            "ja_n": len(agg["ja_order_ids"]),
        }
        score, parts = score_seller(stats)
        route = route_seller(score, n)
        promised_med = median(agg["promised"])
        p90 = quantile(agg["transits"], 0.9)
        rec_promise, reset = recommended_promise_days(p90, promised_med)
        meta = sellers_meta.get(sid, {"seller_city": "unknown", "seller_state": "??"})
        row = {
            "seller_id": sid,
            "seller_state": meta["seller_state"],
            "seller_city": meta["seller_city"],
            "orders": n,
            "late_orders": late_orders,
            "late_rate": stats["late_rate"],
            "median_slip": median(agg["slips"]),
            "late_median_slip": stats["late_median_slip"],
            "max_slip": stats["max_slip"],
            "worst_order_id": agg["worst_order_id"],
            "breach_orders": agg["breach"],
            "breach_rate": stats["breach_rate"],
            "sep_late_rate": stats["sep_late_rate"],
            "sep_n": stats["sep_n"],
            "ja_late_rate": stats["ja_late_rate"],
            "ja_n": stats["ja_n"],
            "promised_median_days": promised_med,
            "p90_transit_days": p90,
            "recommended_promise_days": rec_promise,
            "reset_lead_time": reset,
            "overdue_open": overdue_by_seller.get(sid, 0),
            "score": score,
            "score_parts": parts,
            "route": route,
        }
        action, instruction = recommended_action(row)
        row["action"] = action
        row["instruction"] = instruction
        scored.append(row)

    scored.sort(key=lambda r: (-r["score"], -r["orders"]))
    queue = scored[:QUEUE_N]

    queue_doc = {
        "window": {"start": WINDOW_START, "end": WINDOW_END, "label": "Q3 2017 purchases"},
        "snapshot_date": SNAPSHOT_DATE,
        "delivered_orders": window_orders,
        "late_orders": window_late,
        "late_rate": round(window_late / window_orders, 4) if window_orders else 0.0,
        "total_sellers_window": len(per_seller),
        "scored_sellers": len(scored),
        "segments": dict(Counter(r["route"] for r in scored)),
        "queue_size": len(queue),
        "sellers": queue,
    }

    monthly_rates = {
        ym: round(sum(1 for x in slips if x > 0) / len(slips), 4)
        for ym, slips in sorted(monthly.items())
        if ym.startswith("2017")
    }
    corpus_doc = {
        "delivered_orders": len(corpus_slips),
        "late_orders": sum(1 for x in corpus_slips if x > 0),
        "late_rate": round(sum(1 for x in corpus_slips if x > 0) / len(corpus_slips), 4),
        "median_slip_days": median(corpus_slips),
        "items_with_carrier_date": corpus_items_with_carrier,
        "ship_limit_breach_items": corpus_breach_items,
        "ship_limit_breach_rate": round(corpus_breach_items / corpus_items_with_carrier, 4)
        if corpus_items_with_carrier
        else 0.0,
        "monthly_late_rate_2017": monthly_rates,
        "overdue_open": overdue_total,
        "window_late_rate_by_month": {
            "2017-07": round(sum(1 for x in monthly.get("2017-07", []) if x > 0) / max(1, len(monthly.get("2017-07", []))), 4),
            "2017-08": round(sum(1 for x in monthly.get("2017-08", []) if x > 0) / max(1, len(monthly.get("2017-08", []))), 4),
            "2017-09": round(sum(1 for x in monthly.get("2017-09", []) if x > 0) / max(1, len(monthly.get("2017-09", []))), 4),
        },
    }

    config_doc = {
        "window": {"start": WINDOW_START, "end": WINDOW_END},
        "snapshot_date": SNAPSHOT_DATE,
        "min_orders": MIN_ORDERS,
        "weights": {
            "late_rate": 0.45,
            "severity_cap_days": 15,
            "breach": 0.20,
            "trend_cap": 10,
            "worst_cap": 10,
        },
        "segments": {"escalate": ESCALATE_SCORE, "at_risk": AT_RISK_SCORE, "watch": WATCH_SCORE},
        "lead_reset_gap_days": LEAD_RESET_GAP,
        "trend_min_orders": 2,
    }

    # ---- golden set ----
    by_id = {r["seller_id"]: r for r in scored}
    entries = []
    for sid in GOLDEN_SELLERS:
        r = by_id.get(sid)
        if r is None:
            print(f"  WARNING: golden seller {sid} not in scored set")
            continue
        entries.append(
            {
                "seller_id": sid,
                "kind": "real",
                "stats": {
                    "n": r["orders"],
                    "late_orders": r["late_orders"],
                    "late_rate": r["late_rate"],
                    "late_median_slip": r["late_median_slip"],
                    "max_slip": r["max_slip"],
                    "breach_rate": r["breach_rate"],
                    "sep_late_rate": r["sep_late_rate"],
                    "sep_n": r["sep_n"],
                    "ja_late_rate": r["ja_late_rate"],
                    "ja_n": r["ja_n"],
                },
                "expected_route": r["route"],
                "expected_score": r["score"],
                "note": f"{r['orders']} orders, {r['late_rate']*100:.1f}% late, "
                f"median late {r['late_median_slip']:.0f}d, breach "
                f"{r['breach_rate']*100:.1f}%, max slip {r['max_slip']:.0f}d",
            }
        )
    # Hand-computed edge cases (scores worked out by hand, see tests).
    entries += [
        {
            "seller_id": "edge-all-on-time",
            "kind": "synthetic",
            "stats": {"n": 10, "late_orders": 0, "late_rate": 0.0, "late_median_slip": 0.0,
                      "max_slip": -5.0, "breach_rate": 0.0, "sep_late_rate": 0.0,
                      "sep_n": 5, "ja_late_rate": 0.0, "ja_n": 5},
            "expected_route": "RELIABLE", "expected_score": 0.0,
            "note": "10 orders, none late, none breached: 0 + 0 + 0 + 0 + 0 = 0",
        },
        {
            "seller_id": "edge-single-late",
            "kind": "synthetic",
            "stats": {"n": 10, "late_orders": 1, "late_rate": 0.1, "late_median_slip": 3.0,
                      "max_slip": 3.0, "breach_rate": 0.0, "sep_late_rate": 0.0,
                      "sep_n": 2, "ja_late_rate": 0.125, "ja_n": 8},
            "expected_route": "RELIABLE", "expected_score": 7.5,
            "note": "4.5 late + 3 severity + 0 breach + 0 trend (Sep better) + 0 worst = 7.5",
        },
        {
            "seller_id": "edge-half-late",
            "kind": "synthetic",
            "stats": {"n": 10, "late_orders": 5, "late_rate": 0.5, "late_median_slip": 10.0,
                      "max_slip": 12.0, "breach_rate": 0.2, "sep_late_rate": 0.6,
                      "sep_n": 5, "ja_late_rate": 0.4, "ja_n": 5},
            "expected_route": "ESCALATE", "expected_score": 49.0,
            "note": "22.5 + 10 + 4 + 10 trend + 2.5 worst = 49.0",
        },
        {
            "seller_id": "edge-unscored",
            "kind": "synthetic",
            "stats": {"n": 3, "late_orders": 2, "late_rate": 0.667, "late_median_slip": 9.0,
                      "max_slip": 12.0, "breach_rate": 0.5, "sep_late_rate": 1.0,
                      "sep_n": 2, "ja_late_rate": 0.0, "ja_n": 1},
            "expected_route": "UNSCORED", "expected_score": 51.5,
            "note": "Score still computes (30 late + 9 severity + 10 breach + "
            "0 trend — only 1 Jul-Aug order — + 2.5 worst = 51.5) but the route "
            "is UNSCORED under 5 orders.",
        },
        {
            "seller_id": "edge-trend-guard",
            "kind": "synthetic",
            "stats": {"n": 6, "late_orders": 2, "late_rate": 0.333, "late_median_slip": 5.0,
                      "max_slip": 8.0, "breach_rate": 0.0, "sep_late_rate": 1.0,
                      "sep_n": 1, "ja_late_rate": 0.0, "ja_n": 5},
            "expected_route": "WATCH", "expected_score": 20.5,
            "note": "15 + 5 + 0 + 0 trend (only 1 Sep order) + 0.5 worst = 20.5",
        },
    ]
    golden_doc = {"entries": entries}

    # ---- test vectors (Python/TS contract) ----
    vector_inputs = [
        {"n": 6, "late_orders": 4, "late_rate": 0.667, "late_median_slip": 14.5,
         "max_slip": 19.0, "breach_rate": 0.833, "sep_late_rate": 0.667,
         "sep_n": 3, "ja_late_rate": 0.0, "ja_n": 3},
        {"n": 11, "late_orders": 4, "late_rate": 0.333, "late_median_slip": 14.0,
         "max_slip": 25.0, "breach_rate": 0.25, "sep_late_rate": 1.0,
         "sep_n": 4, "ja_late_rate": 0.2, "ja_n": 7},
        {"n": 18, "late_orders": 5, "late_rate": 0.286, "late_median_slip": 7.0,
         "max_slip": 11.0, "breach_rate": 0.714, "sep_late_rate": 0.444,
         "sep_n": 9, "ja_late_rate": 0.167, "ja_n": 9},
        {"n": 76, "late_orders": 2, "late_rate": 0.021, "late_median_slip": 57.5,
         "max_slip": 109.0, "breach_rate": 0.053, "sep_late_rate": 0.0,
         "sep_n": 20, "ja_late_rate": 0.03, "ja_n": 56},
        {"n": 261, "late_orders": 7, "late_rate": 0.026, "late_median_slip": 4.0,
         "max_slip": 65.0, "breach_rate": 0.014, "sep_late_rate": 0.02,
         "sep_n": 80, "ja_late_rate": 0.03, "ja_n": 181},
        {"n": 10, "late_orders": 0, "late_rate": 0.0, "late_median_slip": 0.0,
         "max_slip": -5.0, "breach_rate": 0.0, "sep_late_rate": 0.0,
         "sep_n": 5, "ja_late_rate": 0.0, "ja_n": 5},
        {"n": 10, "late_orders": 5, "late_rate": 0.5, "late_median_slip": 10.0,
         "max_slip": 12.0, "breach_rate": 0.2, "sep_late_rate": 0.6,
         "sep_n": 5, "ja_late_rate": 0.4, "ja_n": 5},
        {"n": 3, "late_orders": 2, "late_rate": 0.667, "late_median_slip": 9.0,
         "max_slip": 12.0, "breach_rate": 0.5, "sep_late_rate": 1.0,
         "sep_n": 2, "ja_late_rate": 0.0, "ja_n": 1},
        {"n": 14, "late_orders": 1, "late_rate": 0.071, "late_median_slip": 60.0,
         "max_slip": 60.0, "breach_rate": 0.071, "sep_late_rate": 0.25,
         "sep_n": 4, "ja_late_rate": 0.0, "ja_n": 10},
        {"n": 32, "late_orders": 4, "late_rate": 0.132, "late_median_slip": 12.0,
         "max_slip": 23.0, "breach_rate": 0.0, "sep_late_rate": 0.286,
         "sep_n": 7, "ja_late_rate": 0.097, "ja_n": 25},
        {"n": 5, "late_orders": 1, "late_rate": 0.2, "late_median_slip": 8.0,
         "max_slip": 8.0, "breach_rate": 0.4, "sep_late_rate": 0.5,
         "sep_n": 2, "ja_late_rate": 0.0, "ja_n": 3},
        {"n": 20, "late_orders": 0, "late_rate": 0.0, "late_median_slip": 0.0,
         "max_slip": 2.0, "breach_rate": 0.1, "sep_late_rate": 0.0,
         "sep_n": 6, "ja_late_rate": 0.0, "ja_n": 14},
    ]
    vectors = []
    for i, vi in enumerate(vector_inputs):
        score, parts = score_seller(vi)
        route = route_seller(score, vi["n"])
        probe = {
            "seller_id": f"vector-{i}",
            "seller_state": "SP",
            "seller_city": "sao paulo",
            "orders": vi["n"],
            "late_orders": vi["late_orders"],
            "late_rate": vi["late_rate"],
            "median_slip": -10.0,
            "late_median_slip": vi["late_median_slip"],
            "max_slip": vi["max_slip"],
            "worst_order_id": "vector-order",
            "breach_orders": round(vi["breach_rate"] * vi["n"]),
            "breach_rate": vi["breach_rate"],
            "sep_late_rate": vi["sep_late_rate"],
            "ja_late_rate": vi["ja_late_rate"],
            "promised_median_days": 22.0,
            "p90_transit_days": 24.0,
            "recommended_promise_days": 24,
            "reset_lead_time": False,
            "overdue_open": 0,
            "score": score,
            "score_parts": parts,
            "route": route,
        }
        action, _ = recommended_action(probe)
        vectors.append({"input": vi, "expected": {"score": score, "parts": parts, "route": route, "action": action}})
    vectors_doc = {"vectors": vectors}

    for name, doc in [
        ("queue.json", queue_doc),
        ("corpus_stats.json", corpus_doc),
        ("scoring-config.json", config_doc),
        ("golden_set.json", golden_doc),
        ("test-vectors.json", vectors_doc),
    ]:
        with open(RAW / name, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1)
        print(f"  wrote {name}")

    print(f"\nQ3 window: {window_orders} delivered orders, {window_late} late "
          f"({window_late / window_orders:.1%}), {len(per_seller)} sellers, "
          f"{len(scored)} scored, queue {len(queue)}")
    print(f"Overdue as of {SNAPSHOT_DATE}: {overdue_total} orders")
    by_route = Counter(r["route"] for r in scored)
    print("Segments (scored sellers):", dict(by_route))
    print("Top 5 by score:")
    for r in scored[:5]:
        print(f"  {r['seller_id'][:8]} n={r['orders']} late={r['late_rate']:.1%} "
              f"breach={r['breach_rate']:.1%} score={r['score']} {r['route']} "
              f"reset={r['reset_lead_time']}")
    print("Golden sellers (verify by hand):")
    for e in entries:
        if e["kind"] == "real":
            print(f"  {e['seller_id'][:8]}: {e['note']} -> {e['expected_route']} "
                  f"(score {e['expected_score']})")
    print(f"Lead-time resets in queue: {sum(1 for r in queue if r['reset_lead_time'])}")


if __name__ == "__main__":
    main()
