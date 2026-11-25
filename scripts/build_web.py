#!/usr/bin/env python3
"""Run the SlipDesk LangGraph pipeline and write the web payloads.

Outputs (web/public/data/):
  summary.json      — window/corpus headline numbers
  sellers.json      — the top-100 seller queue (export pack)
  slipbook.json     — scoring rules + queue/corpus counts per rule
  test-vectors.json — shared Python/TS contract vectors
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
sys.path.insert(0, str(ROOT / "src"))

from slipdesk.data import load_config, load_corpus, load_vectors  # noqa: E402
from slipdesk.graph import run  # noqa: E402
from slipdesk.report import findings  # noqa: E402


def main() -> None:
    state = run()
    pack = state["export_pack"]
    f = findings()
    corpus = load_corpus()
    config = load_config()

    out = WEB / "public" / "data"
    out.mkdir(parents=True, exist_ok=True)

    summary = {
        "window": f["window"],
        "snapshot": f["snapshot"],
        "queue_size": f["queue_size"],
        "scored_sellers": f["scored_sellers"],
        "total_sellers_window": f["total_sellers_window"],
        "delivered_orders": f["delivered_orders"],
        "late_orders": f["late_orders"],
        "late_rate": f["late_rate"],
        "by_route": f["by_route"],
        "reset_lead_time_count": f["reset_lead_time_count"],
        "overdue_open_in_queue": f["overdue_open_in_queue"],
        "overdue_open_corpus": f["overdue_open_corpus"],
        "corpus": {
            "delivered_orders": corpus["delivered_orders"],
            "late_orders": corpus["late_orders"],
            "late_rate": corpus["late_rate"],
            "median_slip_days": corpus["median_slip_days"],
            "ship_limit_breach_rate": corpus["ship_limit_breach_rate"],
            "monthly_late_rate_2017": corpus["monthly_late_rate_2017"],
            "window_late_rate_by_month": corpus["window_late_rate_by_month"],
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    (out / "sellers.json").write_text(json.dumps(pack, indent=1), encoding="utf-8")

    slipbook = {
        "rules": [
            {
                "id": "late_rate",
                "name": "Late rate",
                "detail": "Share of delivered orders arriving after the promised date, x 100 x 0.45 (max 45 pts).",
                "queue_count": sum(1 for s in pack if s["score_parts"]["late_rate"] > 0),
                "corpus_note": f"{corpus['late_rate'] * 100:.2f}% of all {corpus['delivered_orders']:,} delivered orders arrived late.",
            },
            {
                "id": "severity",
                "name": "Severity",
                "detail": "Median slip among the seller's late orders, capped at 15 days (max 15 pts).",
                "queue_count": sum(1 for s in pack if s["score_parts"]["severity"] > 0),
                "corpus_note": f"Median slip across the corpus is {corpus['median_slip_days']:.0f} days (promises are padded — most orders arrive early).",
            },
            {
                "id": "breach",
                "name": "Ship-limit breach",
                "detail": "Share of items handed to the carrier after the shipping-limit date, x 100 x 0.20 (max 20 pts).",
                "queue_count": sum(1 for s in pack if s["score_parts"]["breach"] > 0),
                "corpus_note": f"{corpus['ship_limit_breach_rate'] * 100:.2f}% of items breached the shipping limit.",
            },
            {
                "id": "trend",
                "name": "September trend",
                "detail": "September late rate minus Jul-Aug late rate, in points, floored at 0 and capped at 10; needs >= 2 orders on each side (max 10 pts).",
                "queue_count": sum(1 for s in pack if s["score_parts"]["trend"] > 0),
                "corpus_note": "Late rate rose from 2.9% (Jul-Aug) to 4.4% (Sep) across the window.",
            },
            {
                "id": "worst",
                "name": "Worst slip",
                "detail": "min(10, max(0, worst slip - 7) / 2): a single catastrophic slip is worth a look even when the seller is usually on time (max 10 pts).",
                "queue_count": sum(1 for s in pack if s["score_parts"]["worst"] > 0),
                "corpus_note": "Worst single slip in the corpus: 188 days late.",
            },
        ],
        "segments": config["segments"],
        "min_orders": config["min_orders"],
        "lead_reset_gap_days": config["lead_reset_gap_days"],
    }
    (out / "slipbook.json").write_text(json.dumps(slipbook, indent=1), encoding="utf-8")

    vectors = load_vectors()
    (out / "test-vectors.json").write_text(json.dumps(vectors, indent=1), encoding="utf-8")

    print(f"build_web: {len(pack)} sellers, summary + slipbook + vectors written")


if __name__ == "__main__":
    main()
