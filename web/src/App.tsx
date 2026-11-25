import { useState } from "react";
import { useSlipDeskData } from "./data";
import QueueView from "./views/QueueView";
import SlipbookView from "./views/SlipbookView";
import PasteView from "./views/PasteView";
import MethodologyView from "./views/MethodologyView";
import "./styles.css";

const REPO_URL = "https://github.com/tidaaartorhem/ai-slipdesk-agent";
const LIVE_URL = "https://ai-slipdesk-agent.web.app";

type Tab = "queue" | "slipbook" | "paste" | "methodology";

const TABS: { id: Tab; label: string }[] = [
  { id: "queue", label: "Seller queue" },
  { id: "slipbook", label: "Slipbook" },
  { id: "paste", label: "Paste a seller" },
  { id: "methodology", label: "Methodology" },
];

export default function App() {
  const { data, error } = useSlipDeskData();
  const [tab, setTab] = useState<Tab>("queue");

  if (error) {
    return (
      <div className="app">
        <div className="card">
          <h2>Could not load SlipDesk data</h2>
          <p className="muted">{error}</p>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="app">
        <div className="card">
          <p className="muted">Loading the Q3 2017 slip desk…</p>
        </div>
      </div>
    );
  }

  const s = data.summary;
  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>
            <span className="mark">Sl</span>SlipDesk
          </h1>
          <p className="sub">
            The supplier lead-time slip desk for Meridian Marketplace: every seller&apos;s promise
            against what actually arrived, scored and queued for the morning chase. Q3 2017 replay,
            snapshot Oct 31, 2017. Every action is a human-gated draft — nothing is sent without
            approval.
          </p>
          <div className="badges">
            <span className="badge neutral">
              <a href={REPO_URL} target="_blank" rel="noreferrer">
                GitHub repo
              </a>
            </span>
            <span className="badge neutral">
              <a href={LIVE_URL} target="_blank" rel="noreferrer">
                Live site
              </a>
            </span>
            {data.stamp && (
              <span className="badge neutral" title={data.stamp.pipeline}>
                built {data.stamp.git_sha} · {data.stamp.built_utc.slice(0, 10)}
              </span>
            )}
          </div>
        </div>
      </header>

      <div className="disclosure banner">
        <b>Deterministic, no LLM.</b> Slip is delivered date minus promised date, in days. Score
        0–100: late rate × 0.45 + severity (median late slip, capped 15) + ship-limit breach × 0.20 +
        September trend (max 10) + worst slip (max 10). Route: score ≥ 45 ESCALATE · ≥ 30 AT_RISK ·
        ≥ 12 WATCH · otherwise RELIABLE. The in-browser scorer mirrors the Python pipeline exactly.
      </div>

      <div className="card">
        <div className="summary-row">
          <div className="summary">
            <span className="summary-num">{(s.late_rate * 100).toFixed(1)}%</span>
            <span className="summary-label">of Q3 orders late</span>
          </div>
          <div className="summary">
            <span className="summary-num bad">{s.by_route.ESCALATE ?? 0}</span>
            <span className="summary-label">escalate</span>
          </div>
          <div className="summary">
            <span className="summary-num">{s.by_route.AT_RISK ?? 0}</span>
            <span className="summary-label">at risk</span>
          </div>
          <div className="summary">
            <span className="summary-num">{s.reset_lead_time_count}</span>
            <span className="summary-label">lead-time resets</span>
          </div>
          <div className="summary">
            <span className="summary-num">{s.overdue_open_corpus}</span>
            <span className="summary-label">orders still overdue</span>
          </div>
          <div className="summary">
            <span className="summary-num">{s.scored_sellers}</span>
            <span className="summary-label">sellers scored</span>
          </div>
        </div>
        <p className="muted small" style={{ marginBottom: 0 }}>
          {s.delivered_orders.toLocaleString("en-US")} delivered orders in Q3 2017 · {s.late_orders}{" "}
          late · {s.total_sellers_window} sellers in the window · late rate rose Jul{" "}
          {(s.corpus.window_late_rate_by_month["2017-07"] * 100).toFixed(1)}% → Aug{" "}
          {(s.corpus.window_late_rate_by_month["2017-08"] * 100).toFixed(1)}% → Sep{" "}
          {(s.corpus.window_late_rate_by_month["2017-09"] * 100).toFixed(1)}%
        </p>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
            {t.id === "queue" && <span className="count">{data.sellers.length}</span>}
          </button>
        ))}
      </div>

      {tab === "queue" && <QueueView data={data} />}
      {tab === "slipbook" && <SlipbookView data={data} />}
      {tab === "paste" && <PasteView data={data} />}
      {tab === "methodology" && <MethodologyView data={data} />}
    </div>
  );
}
