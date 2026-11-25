"""Tests for the SlipDesk pipeline: engine rules, graph end-to-end,
golden-set eval, and the shared Python/TS test-vectors contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slipdesk import eval as sd_eval  # noqa: E402
from slipdesk.data import load_config, load_golden, load_queue, load_vectors  # noqa: E402
from slipdesk.graph import run  # noqa: E402
from slipdesk.report import findings  # noqa: E402
from slipdesk.scoring import (  # noqa: E402
    chase_draft,
    recommended_action,
    recommended_promise_days,
    route_seller,
    score_seller,
)


def _stats(**over) -> dict:
    base = {
        "n": 10,
        "late_orders": 0,
        "late_rate": 0.0,
        "late_median_slip": 0.0,
        "max_slip": -5.0,
        "breach_rate": 0.0,
        "sep_late_rate": 0.0,
        "sep_n": 5,
        "ja_late_rate": 0.0,
        "ja_n": 5,
    }
    base.update(over)
    return base


def test_all_on_time_scores_zero():
    score, parts = score_seller(_stats())
    assert score == 0.0
    assert parts == {"late_rate": 0.0, "severity": 0.0, "breach": 0.0, "trend": 0.0, "worst": 0.0}
    assert route_seller(score, 10) == "RELIABLE"


def test_single_late_order_scores_7_5():
    score, _ = score_seller(
        _stats(late_orders=1, late_rate=0.1, late_median_slip=3.0, max_slip=3.0,
               sep_late_rate=0.0, sep_n=2, ja_late_rate=0.125, ja_n=8)
    )
    assert score == 7.5  # 4.5 + 3 + 0 + 0 + 0


def test_half_late_escalates_at_49():
    score, parts = score_seller(
        _stats(late_orders=5, late_rate=0.5, late_median_slip=10.0, max_slip=12.0,
               breach_rate=0.2, sep_late_rate=0.6, sep_n=5, ja_late_rate=0.4, ja_n=5)
    )
    assert score == 49.0  # 22.5 + 10 + 4 + 10 + 2.5
    assert parts["trend"] == 10.0
    assert route_seller(score, 10) == "ESCALATE"


def test_trend_guard_needs_two_orders_each_side():
    # September looks terrible (100% late) but it is a single order: no trend points.
    score, parts = score_seller(
        _stats(n=6, late_orders=2, late_rate=0.333, late_median_slip=5.0, max_slip=8.0,
               sep_late_rate=1.0, sep_n=1, ja_late_rate=0.0, ja_n=5)
    )
    assert parts["trend"] == 0.0
    assert score == 20.5  # 15 + 5 + 0 + 0 + 0.5
    assert route_seller(score, 6) == "WATCH"


def test_under_five_orders_is_unscored():
    score, _ = score_seller(
        _stats(n=3, late_orders=2, late_rate=0.667, late_median_slip=9.0, max_slip=12.0,
               breach_rate=0.5, sep_late_rate=1.0, sep_n=2, ja_late_rate=0.0, ja_n=1)
    )
    assert score == 51.5
    assert route_seller(score, 3) == "UNSCORED"


def test_catastrophic_single_slip_lifts_reliable_seller_to_watch():
    # 1 late order in 76, but it was 109 days late.
    score, parts = score_seller(
        _stats(n=76, late_orders=2, late_rate=0.026, late_median_slip=57.5, max_slip=109.0,
               breach_rate=0.096, sep_late_rate=0.0, sep_n=20, ja_late_rate=0.03, ja_n=56)
    )
    assert parts["worst"] == 10.0
    assert parts["severity"] == 15.0
    assert route_seller(score, 76) == "WATCH"


def test_segment_boundaries():
    assert route_seller(45.0, 10) == "ESCALATE"
    assert route_seller(44.9, 10) == "AT_RISK"
    assert route_seller(30.0, 10) == "AT_RISK"
    assert route_seller(29.9, 10) == "WATCH"
    assert route_seller(12.0, 10) == "WATCH"
    assert route_seller(11.9, 10) == "RELIABLE"


def test_lead_time_reset_recommendation():
    rec, reset = recommended_promise_days(42.2, 26.0)
    assert rec == 43 and reset is True
    rec, reset = recommended_promise_days(19.0, 27.0)
    assert rec == 19 and reset is False
    rec, reset = recommended_promise_days(24.0, 20.0)
    assert rec == 24 and reset is False  # gap 4 < 5: no reset


def _seller(**over) -> dict:
    base = {
        "seller_id": "test-seller",
        "seller_state": "SP",
        "seller_city": "sao paulo",
        "orders": 10,
        "late_orders": 0,
        "late_rate": 0.0,
        "median_slip": -10.0,
        "late_median_slip": 0.0,
        "max_slip": -5.0,
        "worst_order_id": "o1",
        "breach_orders": 0,
        "breach_rate": 0.0,
        "sep_late_rate": 0.0,
        "ja_late_rate": 0.0,
        "promised_median_days": 22.0,
        "p90_transit_days": 19.0,
        "recommended_promise_days": 19,
        "reset_lead_time": False,
        "overdue_open": 0,
        "score": 0.0,
        "score_parts": {"late_rate": 0.0, "severity": 0.0, "breach": 0.0, "trend": 0.0, "worst": 0.0},
        "route": "RELIABLE",
    }
    base.update(over)
    return base


def test_action_priority_reset_beats_chase():
    s = _seller(route="ESCALATE", reset_lead_time=True, recommended_promise_days=43,
                p90_transit_days=42.2, promised_median_days=26.0, overdue_open=5)
    action, _ = recommended_action(s)
    assert action == "RESET LEAD TIME"


def test_action_overdue_beats_breach():
    s = _seller(route="AT_RISK", overdue_open=4, breach_rate=0.4)
    action, _ = recommended_action(s)
    assert action == "CHASE OVERDUE ORDERS"


def test_action_reliable_is_no_action():
    action, _ = recommended_action(_seller())
    assert action == "NO ACTION"


def test_draft_names_real_numbers_and_is_gated():
    s = _seller(route="ESCALATE", orders=6, late_orders=4, late_rate=0.667,
                late_median_slip=14.5, max_slip=19.0, breach_rate=0.833,
                reset_lead_time=True, recommended_promise_days=43,
                p90_transit_days=42.2, promised_median_days=26.0, overdue_open=1,
                score=67.2,
                score_parts={"late_rate": 30.0, "severity": 14.5, "breach": 16.7, "trend": 0.0, "worst": 6.0})
    draft = chase_draft(s)
    assert "66.7%" in draft
    assert "43 days" in draft
    assert "Nothing has been sent" in draft


def test_golden_set_eval_passes():
    result = sd_eval.evaluate()
    assert result["accuracy"] == 1.0, json.dumps(result["results"], indent=1)


def test_queue_shape_and_segments():
    queue = load_queue()
    assert queue["queue_size"] == 100
    assert queue["scored_sellers"] == 456
    assert queue["delivered_orders"] == 12215
    assert queue["late_orders"] == 412
    sellers = queue["sellers"]
    assert sellers == sorted(sellers, key=lambda s: (-s["score"], -s["orders"]))
    assert sellers[0]["route"] == "ESCALATE"
    assert sellers[0]["seller_id"].startswith("633ecdf8")
    assert sellers[0]["score"] == 67.2
    assert sum(1 for s in sellers if s["reset_lead_time"]) == 25
    assert all(s["orders"] >= 5 for s in sellers)


def test_graph_end_to_end():
    state = run()
    pack = state["export_pack"]
    assert len(pack) == 100
    assert all(p["pending_approval"] is True for p in pack)
    assert all(p["action"] for p in pack)
    assert all("score_parts" in p and "draft" in p for p in pack)
    routes = {p["route"] for p in pack}
    assert {"ESCALATE", "AT_RISK", "WATCH"} <= routes


def test_findings_headlines():
    f = findings()
    assert f["by_route"] == {"ESCALATE": 1, "AT_RISK": 22, "WATCH": 119, "RELIABLE": 314}
    assert f["reset_lead_time_count"] == 25
    assert f["overdue_open_corpus"] == 224
    assert f["corpus"]["late_rate"] == 0.0677


def test_test_vectors_contract_is_self_consistent():
    vectors = load_vectors()["vectors"]
    assert len(vectors) == 12
    for v in vectors:
        score, parts = score_seller(v["input"])
        assert score == v["expected"]["score"]
        assert parts == v["expected"]["parts"]
        assert route_seller(score, v["input"]["n"]) == v["expected"]["route"]


def test_config_matches_scoring_module():
    config = load_config()
    assert config["segments"] == {"escalate": 45, "at_risk": 30, "watch": 12}
    assert config["min_orders"] == 5
