import { useState } from "react";
import type { Route, SellerRow } from "../types";

const ROUTE_CLASS: Record<Route, string> = {
  ESCALATE: "bad",
  AT_RISK: "warn",
  WATCH: "warn",
  RELIABLE: "ok",
  UNSCORED: "neutral",
};

export function RouteBadge({ route }: { route: Route }) {
  return <span className={`pill ${ROUTE_CLASS[route]}`}>{route.replace("_", " ")}</span>;
}

export function ScoreBar({ value }: { value: number }) {
  const cls = value >= 45 ? "bad" : value >= 30 ? "warn" : value >= 12 ? "warn" : "ok";
  return (
    <span className="confbar" title={`${value}`}>
      <span className="confbar-track">
        <span className={`confbar-fill ${cls}`} style={{ width: `${Math.min(100, value)}%` }} />
      </span>
      <span className="confbar-num">{value}</span>
    </span>
  );
}

export function SellerCard({ s }: { s: SellerRow }) {
  const [open, setOpen] = useState(false);
  const parts = s.score_parts;
  return (
    <div className="card match-card">
      <div className="match-head">
        <span className="req-id">#{s.seller_id.slice(0, 8)}</span>
        <RouteBadge route={s.route} />
        <ScoreBar value={s.score} />
        <span className="pill neutral">
          {s.seller_city}, {s.seller_state}
        </span>
        {s.reset_lead_time && <span className="pill warn">reset lead time</span>}
        {s.overdue_open > 0 && <span className="pill bad">{s.overdue_open} overdue</span>}
        <span className="pill gate">human gate required</span>
      </div>
      <p className="req-text">
        <b>
          {s.orders} orders · {(s.late_rate * 100).toFixed(1)}% late · median late slip{" "}
          {s.late_median_slip.toFixed(0)} days · worst {s.max_slip.toFixed(0)} days
        </b>
      </p>
      <div className="muted small" style={{ marginBottom: 8 }}>
        {(s.breach_rate * 100).toFixed(1)}% of items shipped after the shipping-limit date · promised{" "}
        {s.promised_median_days.toFixed(0)} days, p90 actual transit {s.p90_transit_days.toFixed(0)} days
        {s.reset_lead_time ? ` — recommended promise ${s.recommended_promise_days} days` : ""} · Sep late{" "}
        {(s.sep_late_rate * 100).toFixed(0)}% vs Jul–Aug {(s.ja_late_rate * 100).toFixed(0)}%
      </div>
      <div className="action-line">
        <b>Recommended action:</b> {s.action.replace(/_/g, " ")} — {s.instruction}
      </div>
      <button className="btn" style={{ marginTop: 10 }} onClick={() => setOpen(!open)}>
        {open ? "Hide score breakdown and draft" : "Show score breakdown and chase draft"}
      </button>
      {open && (
        <div style={{ marginTop: 12 }}>
          <table className="table">
            <thead>
              <tr>
                <th>Score part</th>
                <th>Points</th>
                <th>How it is measured</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><b>Late rate</b></td>
                <td>{parts.late_rate}</td>
                <td>{s.late_orders} of {s.orders} orders late × 100 × 0.45</td>
              </tr>
              <tr>
                <td><b>Severity</b></td>
                <td>{parts.severity}</td>
                <td>Median slip among late orders ({s.late_median_slip.toFixed(1)} days), capped at 15</td>
              </tr>
              <tr>
                <td><b>Ship-limit breach</b></td>
                <td>{parts.breach}</td>
                <td>{s.breach_orders} items breached × 100 × 0.20</td>
              </tr>
              <tr>
                <td><b>September trend</b></td>
                <td>{parts.trend}</td>
                <td>Sep {(s.sep_late_rate * 100).toFixed(1)}% late vs Jul–Aug {(s.ja_late_rate * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <td><b>Worst slip</b></td>
                <td>{parts.worst}</td>
                <td>Worst order {s.worst_order_id.slice(0, 8)} arrived {s.max_slip.toFixed(0)} days late</td>
              </tr>
            </tbody>
          </table>
          <div className="muted small" style={{ margin: "8px 0" }}>
            Score {s.score} = {parts.late_rate} + {parts.severity} + {parts.breach} + {parts.trend} +{" "}
            {parts.worst} (capped at 100). Route: {s.route} (ESCALATE ≥ 45 · AT_RISK ≥ 30 · WATCH ≥ 12).
          </div>
          <div className="card" style={{ marginTop: 12, background: "#fbfcfe" }}>
            <h3 style={{ marginTop: 0 }}>Chase draft — pending human approval</h3>
            <p className="muted small">
              Nothing here is sent. A person reviews the draft, edits as needed, and approves before
              anything goes to the seller.
            </p>
            <pre className="mono small" style={{ whiteSpace: "pre-wrap" }}>{s.draft}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
