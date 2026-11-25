import type { SlipDeskData } from "../types";

/** The slipbook: the five score parts, what each measures, and corpus counts. */
export default function SlipbookView({ data }: { data: SlipDeskData }) {
  const { slipbook, summary } = data;
  return (
    <div>
      <div className="card">
        <h2>Slipbook</h2>
        <p className="muted">
          Five disclosed parts, all measured from the Olist rows — no LLM calls, no hidden weights.
          Score 0–100: ESCALATE ≥ {slipbook.segments.escalate} · AT_RISK ≥ {slipbook.segments.at_risk} ·
          WATCH ≥ {slipbook.segments.watch} · otherwise RELIABLE. Sellers with fewer than{" "}
          {slipbook.min_orders} delivered orders are UNSCORED — a rate built on 2 orders is noise, not
          a signal. Lead time resets when the recommended promise beats the current promise by ≥{" "}
          {slipbook.lead_reset_gap_days} days.
        </p>
        <div className="summary-row">
          <div className="summary">
            <span className="summary-num">{summary.scored_sellers}</span>
            <span className="summary-label">sellers scored</span>
          </div>
          <div className="summary">
            <span className="summary-num">{summary.by_route.ESCALATE ?? 0}</span>
            <span className="summary-label">escalate</span>
          </div>
          <div className="summary">
            <span className="summary-num">{summary.by_route.AT_RISK ?? 0}</span>
            <span className="summary-label">at risk</span>
          </div>
          <div className="summary">
            <span className="summary-num">{summary.reset_lead_time_count}</span>
            <span className="summary-label">lead-time resets</span>
          </div>
          <div className="summary">
            <span className="summary-num">{summary.overdue_open_corpus}</span>
            <span className="summary-label">orders still overdue Oct 31</span>
          </div>
        </div>
      </div>
      {slipbook.rules.map((r) => (
        <div className="card" key={r.id}>
          <h2>{r.name}</h2>
          <p className="muted">{r.detail}</p>
          <div className="muted small">
            In the queue: <b>{r.queue_count} of {summary.queue_size} sellers</b> score on this part.
          </div>
          <div className="muted small">{r.corpus_note}</div>
        </div>
      ))}
    </div>
  );
}
