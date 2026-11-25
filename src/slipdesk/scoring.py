"""SlipDesk scoring: promise-vs-actual delivery performance per seller.

The unit of analysis is the SELLER, not the order. For every delivered
order in the replay window we measure

  slip_days = delivered_customer_date - estimated_delivery_date
              (positive = the order arrived AFTER the promised date)

and a ship-limit breach (delivered_carrier_date after the item's
shipping_limit_date). A seller's slip-risk score (0-100) is five disclosed
parts, all computed from measured rates and days — no LLM calls:

  late_rate  late share of delivered orders x 100 x 0.45      (max 45)
  severity   median slip among late orders, capped at 15 days  (max 15)
  breach     ship-limit breach share x 100 x 0.20             (max 20)
  trend      Sep late rate minus Jul-Aug late rate, in points,
             floored at 0 and capped at 10; only when the seller has
             >=2 delivered orders in each side of the split         (max 10)
  worst      min(10, max(0, worst slip - 7) / 2) — a single
             catastrophic slip (e.g. 65 days late) is worth a look
             even when the seller is usually on time                (max 10)

Segments: score >= 45 ESCALATE, >= 30 AT_RISK, >= 12 WATCH, else RELIABLE.
Sellers with fewer than MIN_ORDERS delivered orders are UNSCORED — a
rate built on 2 orders is noise, not a signal.
"""
from __future__ import annotations

WINDOW_START = "2017-07-01"
WINDOW_END = "2017-10-01"  # exclusive; purchases in Q3 2017
SNAPSHOT_DATE = "2017-10-31"  # "still waiting" judged as of this date
MIN_ORDERS = 5
TREND_MIN_ORDERS = 2

LATE_RATE_WEIGHT = 0.45
SEVERITY_CAP = 15.0
BREACH_WEIGHT = 0.20
TREND_CAP = 10.0
WORST_CAP = 10.0

ESCALATE_SCORE = 45
AT_RISK_SCORE = 30
WATCH_SCORE = 12

LEAD_RESET_GAP = 5  # recommended promise must exceed the current promise by >= 5 days


def score_seller(stats: dict) -> tuple[float, dict]:
    """Return (score, parts) for a seller's window aggregates.

    stats keys: n, late_orders, late_rate, late_median_slip, max_slip,
    breach_rate, sep_late_rate, sep_n, ja_late_rate, ja_n.
    """
    late_rate = float(stats.get("late_rate", 0.0))
    late_median = float(stats.get("late_median_slip", 0.0) or 0.0)
    breach_rate = float(stats.get("breach_rate", 0.0))
    max_slip = float(stats.get("max_slip", 0.0) or 0.0)
    sep_n = int(stats.get("sep_n", 0))
    ja_n = int(stats.get("ja_n", 0))
    sep_late = float(stats.get("sep_late_rate", 0.0))
    ja_late = float(stats.get("ja_late_rate", 0.0))

    p_late = round(late_rate * 100 * LATE_RATE_WEIGHT, 1)
    p_severity = round(min(SEVERITY_CAP, max(0.0, late_median)), 1)
    p_breach = round(breach_rate * 100 * BREACH_WEIGHT, 1)
    if sep_n >= TREND_MIN_ORDERS and ja_n >= TREND_MIN_ORDERS:
        p_trend = round(max(0.0, min(TREND_CAP, (sep_late - ja_late) * 100)), 1)
    else:
        p_trend = 0.0
    p_worst = round(min(WORST_CAP, max(0.0, max_slip - 7) / 2), 1)

    parts = {
        "late_rate": p_late,
        "severity": p_severity,
        "breach": p_breach,
        "trend": p_trend,
        "worst": p_worst,
    }
    return round(sum(parts.values()), 1), parts


def route_seller(score: float, n: int) -> str:
    if n < MIN_ORDERS:
        return "UNSCORED"
    if score >= ESCALATE_SCORE:
        return "ESCALATE"
    if score >= AT_RISK_SCORE:
        return "AT_RISK"
    if score >= WATCH_SCORE:
        return "WATCH"
    return "RELIABLE"


def recommended_promise_days(p90_transit_days: float, promised_median_days: float) -> tuple[int, bool]:
    """Recommended promise = ceil(p90 actual transit). Reset when it beats
    the current promise by at least LEAD_RESET_GAP days."""
    import math

    rec = int(math.ceil(float(p90_transit_days)))
    return rec, (rec - float(promised_median_days)) >= LEAD_RESET_GAP


def recommended_action(seller: dict) -> tuple[str, str]:
    """One recommended action per seller, highest-priority signal first."""
    route = seller["route"]
    if route in ("UNSCORED", "RELIABLE"):
        return ("NO ACTION", "Promise is holding. No chase, no lead-time change.")
    rec = seller["recommended_promise_days"]
    promised = seller["promised_median_days"]
    if seller.get("reset_lead_time") and route in ("ESCALATE", "AT_RISK"):
        return (
            "RESET LEAD TIME",
            f"Reset the promised lead time from {promised} to {rec} days: "
            f"p90 actual transit is {seller['p90_transit_days']} days, so the "
            f"current promise is unkeepable.",
        )
    if seller.get("overdue_open", 0) >= 3:
        return (
            "CHASE OVERDUE ORDERS",
            f"{seller['overdue_open']} orders are past their promised date and "
            f"still not delivered as of {SNAPSHOT_DATE}. Chase the seller today.",
        )
    if seller["breach_rate"] >= 0.25:
        return (
            "FIX SHIP-BY DISCIPLINE",
            f"{seller['breach_rate'] * 100:.0f}% of items shipped after the "
            f"shipping-limit date. The slip starts in the warehouse, not with "
            f"the carrier.",
        )
    if seller["late_rate"] >= 0.20:
        return (
            "CHASE AND COACH",
            f"{seller['late_rate'] * 100:.0f}% of delivered orders arrived late "
            f"(median {seller['late_median_slip']:.0f} days late). Call the seller, "
            f"agree a backlog plan, and re-check in two weeks.",
        )
    if seller["score_parts"]["trend"] >= TREND_CAP:
        return (
            "CHECK SEPTEMBER CAPACITY",
            f"Late rate jumped in September ({seller['sep_late_rate'] * 100:.0f}% "
            f"vs {seller['ja_late_rate'] * 100:.0f}% in Jul-Aug). Something changed "
            f"last month — capacity, staffing, or a new product line.",
        )
    if seller["score_parts"]["worst"] >= WORST_CAP:
        return (
            "REVIEW THE CATASTROPHIC SLIP",
            f"One order arrived {seller['max_slip']:.0f} days late "
            f"(order {seller['worst_order_id']}). The rate looks fine; the tail "
            f"does not. Find out what happened before it repeats.",
        )
    if route == "WATCH":
        return (
            "MONITOR",
            "Below the action bar, but the slip pattern is visible. Re-score next "
            "month; no chase today.",
        )
    return (
        "CHASE THE SELLER",
        f"Late rate {seller['late_rate'] * 100:.0f}% with median late slip "
        f"{seller['late_median_slip']:.0f} days. Chase and set a check-in date.",
    )


def chase_draft(seller: dict) -> str:
    """Human-gated chase note. A draft only — nothing is sent."""
    action, instruction = recommended_action(seller)
    lines = [
        f"Subject: Delivery performance — {seller['seller_id'][:8]} "
        f"({seller['seller_city']}, {seller['seller_state']})",
        "",
        f"Hi team,",
        "",
        f"In Q3 2017 this seller delivered {seller['orders']} orders. "
        f"{seller['late_orders']} arrived after the promised date "
        f"({seller['late_rate'] * 100:.1f}% late, median "
        f"{seller['late_median_slip']:.0f} days late, worst "
        f"{seller['max_slip']:.0f} days). "
        f"{seller['breach_rate'] * 100:.1f}% of items shipped after the "
        f"shipping-limit date.",
    ]
    if seller.get("overdue_open"):
        lines.append(
            f"{seller['overdue_open']} order(s) are still past their promised "
            f"date and undelivered as of {SNAPSHOT_DATE}."
        )
    if seller.get("reset_lead_time"):
        lines.append(
            f"Recommended promise: {seller['recommended_promise_days']} days "
            f"(current median promise {seller['promised_median_days']} days, "
            f"p90 actual transit {seller['p90_transit_days']} days)."
        )
    lines += [
        "",
        f"Recommended action: {action} — {instruction}",
        "",
        "This is a draft for a human to approve. Nothing has been sent.",
    ]
    return "\n".join(lines)
