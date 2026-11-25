import { useState } from "react";
import type { SellerRow, SlipDeskData } from "../types";
import { chaseDraft, recommendedAction, recommendedPromiseDays, routeSeller, scoreSeller } from "../rules";

/** Paste-a-seller: the same scoring runs in the browser via the TS mirror. */
export default function PasteView({ data }: { data: SlipDeskData }) {
  const [orders, setOrders] = useState(12);
  const [lateOrders, setLateOrders] = useState(4);
  const [lateMedian, setLateMedian] = useState(7);
  const [maxSlip, setMaxSlip] = useState(11);
  const [breachItems, setBreachItems] = useState(9);
  const [itemCount, setItemCount] = useState(14);
  const [sepOrders, setSepOrders] = useState(5);
  const [sepLate, setSepLate] = useState(3);
  const [jaOrders, setJaOrders] = useState(7);
  const [jaLate, setJaLate] = useState(1);
  const [promised, setPromised] = useState(21);
  const [p90, setP90] = useState(33);
  const [overdue, setOverdue] = useState(0);
  const [ran, setRan] = useState(false);

  const stats = {
    n: orders,
    late_orders: lateOrders,
    late_rate: orders > 0 ? lateOrders / orders : 0,
    late_median_slip: lateMedian,
    max_slip: maxSlip,
    breach_rate: itemCount > 0 ? breachItems / itemCount : 0,
    sep_late_rate: sepOrders > 0 ? sepLate / sepOrders : 0,
    sep_n: sepOrders,
    ja_late_rate: jaOrders > 0 ? jaLate / jaOrders : 0,
    ja_n: jaOrders,
  };
  const { score, parts } = scoreSeller(stats);
  const route = routeSeller(score, orders);
  const { rec, reset } = recommendedPromiseDays(p90, promised);
  const probe: SellerRow = {
    seller_id: "pasted-seller",
    seller_state: "SP",
    seller_city: "pasted",
    orders,
    late_orders: lateOrders,
    late_rate: stats.late_rate,
    median_slip: -10,
    late_median_slip: lateMedian,
    max_slip: maxSlip,
    worst_order_id: "pasted-order",
    breach_orders: breachItems,
    breach_rate: stats.breach_rate,
    sep_late_rate: stats.sep_late_rate,
    sep_n: sepOrders,
    ja_late_rate: stats.ja_late_rate,
    ja_n: jaOrders,
    promised_median_days: promised,
    p90_transit_days: p90,
    recommended_promise_days: rec,
    reset_lead_time: reset,
    overdue_open: overdue,
    score,
    score_parts: parts,
    route,
    action: "",
    instruction: "",
    draft: "",
    pending_approval: true,
  };
  const { action, instruction } = recommendedAction(probe);
  probe.action = action;
  probe.instruction = instruction;
  probe.draft = chaseDraft(probe);

  const num = (label: string, value: number, set: (n: number) => void, min = 0) => (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        min={min}
        value={value}
        onChange={(e) => set(Math.max(min, Number(e.target.value) || 0))}
      />
    </label>
  );

  return (
    <div>
      <div className="card">
        <h2>Paste a seller</h2>
        <p className="muted">
          Enter a seller&apos;s Q3 2017 window numbers and the same scoring runs here in the browser —
          the TypeScript mirror of the Python pipeline. It agrees with the Python engine on all{" "}
          {data.vectors.vectors.length} shared test vectors. Nothing leaves the browser.
        </p>
        <div className="form-grid">
          {num("Delivered orders", orders, setOrders)}
          {num("Late orders (arrived after the promised date)", lateOrders, setLateOrders)}
          {num("Median slip among late orders (days)", lateMedian, setLateMedian)}
          {num("Worst slip (days)", maxSlip, setMaxSlip)}
          {num("Items shipped after the shipping-limit date", breachItems, setBreachItems)}
          {num("Total items", itemCount, setItemCount)}
          {num("September orders", sepOrders, setSepOrders)}
          {num("September late orders", sepLate, setSepLate)}
          {num("Jul–Aug orders", jaOrders, setJaOrders)}
          {num("Jul–Aug late orders", jaLate, setJaLate)}
          {num("Median promised lead time (days)", promised, setPromised)}
          {num("P90 actual transit (days)", p90, setP90)}
          {num("Orders still overdue", overdue, setOverdue)}
        </div>
        <button className="btn" style={{ marginTop: 12 }} onClick={() => setRan(true)}>
          Score this seller
        </button>
      </div>
      {ran && (
        <div className="card">
          <h2>
            Score {score} — {route.replace("_", " ")}
          </h2>
          <p className="muted">
            Late {parts.late_rate} + severity {parts.severity} + breach {parts.breach} + trend{" "}
            {parts.trend} + worst {parts.worst}. Recommended promise: {rec} days
            {reset ? " — reset the lead time, the current promise is unkeepable." : " — promise holds."}
          </p>
          <div className="action-line">
            <b>Recommended action:</b> {action.replace(/_/g, " ")} — {instruction}
          </div>
          <h3>Chase draft — pending human approval</h3>
          <pre className="mono small" style={{ whiteSpace: "pre-wrap" }}>{probe.draft}</pre>
        </div>
      )}
    </div>
  );
}
