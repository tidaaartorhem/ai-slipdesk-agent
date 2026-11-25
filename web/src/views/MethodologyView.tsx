import type { SlipDeskData } from "../types";

/** Methodology: what the desk measures, where the numbers come from, and what it cannot see. */
export default function MethodologyView({ data }: { data: SlipDeskData }) {
  const { summary } = data;
  const c = summary.corpus;
  return (
    <div>
      <div className="card">
        <h2>Methodology</h2>
        <p className="muted">
          SlipDesk is the supplier lead-time slip desk for Meridian Marketplace, a fictional
          marketplace operator. It watches one thing: does each seller keep the delivery promise the
          customer was given? The replay covers purchases from Jul 1 to Sep 30, 2017, with the
          snapshot as of Oct 31, 2017.
        </p>
        <h3>Data — real, not seeded</h3>
        <p className="muted">
          The{" "}
          <a href="https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce" target="_blank" rel="noreferrer">
            Olist Brazilian E-Commerce dataset
          </a>{" "}
          (Kaggle, CC BY 4.0), via the zero-auth mirror at github.com/olist/work-at-olist-data:{" "}
          {c.delivered_orders.toLocaleString("en-US")} delivered orders, {c.late_orders.toLocaleString("en-US")}{" "}
          of them late ({(c.late_rate * 100).toFixed(2)}%). The promise is{" "}
          <code>order_estimated_delivery_date</code>; the actual is{" "}
          <code>order_delivered_customer_date</code>. Slip is actual minus promise, in days. The
          ship-limit breach uses each item&apos;s <code>shipping_limit_date</code> against{" "}
          <code>order_delivered_carrier_date</code>. Meridian Marketplace is fictional; the Olist rows
          are real.
        </p>
        <h3>What it found</h3>
        <p className="muted">
          In Q3 2017, {summary.delivered_orders.toLocaleString("en-US")} orders were delivered and{" "}
          {summary.late_orders} arrived late ({(summary.late_rate * 100).toFixed(1)}%). The late rate
          rose through the quarter — Jul{" "}
          {(c.window_late_rate_by_month["2017-07"] * 100).toFixed(1)}%, Aug{" "}
          {(c.window_late_rate_by_month["2017-08"] * 100).toFixed(1)}%, Sep{" "}
          {(c.window_late_rate_by_month["2017-09"] * 100).toFixed(1)}% — which is why the score has a
          trend part. {summary.overdue_open_corpus} orders were still past their promised date and
          undelivered as of Oct 31. Across all {summary.scored_sellers} scored sellers:{" "}
          {summary.by_route.ESCALATE ?? 0} ESCALATE, {summary.by_route.AT_RISK ?? 0} AT_RISK,{" "}
          {summary.by_route.WATCH ?? 0} WATCH, {summary.by_route.RELIABLE ?? 0} RELIABLE.{" "}
          {summary.reset_lead_time_count} sellers in the queue need their promised lead time reset
          because their p90 actual transit beats the promise by 5 days or more.
        </p>
        <h3>The score, in full</h3>
        <p className="muted">
          Late rate × 100 × 0.45 (max 45) + median late slip capped at 15 (max 15) + ship-limit breach
          × 100 × 0.20 (max 20) + September trend, floored at 0 and capped at 10 (max 10) + worst slip
          min(10, max(0, worst − 7) / 2) (max 10). Segments: ESCALATE ≥ 45 · AT_RISK ≥ 30 · WATCH ≥ 12.
          Sellers under 5 delivered orders are UNSCORED.
        </p>
        <h3>What it cannot see</h3>
        <p className="muted">
          The promise is padded: the median order arrives 12 days early, so a seller can slip for
          weeks before a single order reads late — the score watches the rate, not the padding. A
          multi-seller order attributes its slip to each seller on it (98% of orders have one
          seller, so this barely moves the numbers). The desk sees delivery dates, not why a seller
          slipped — weather, stock-outs, and carrier failures all look the same here, which is why
          every action is a human-gated draft, never an automated penalty. And the trend part needs
          at least 2 orders on each side of the September split, so a seller with one September order
          cannot earn trend points on a single bad week.
        </p>
        <h3>Pipeline</h3>
        <p className="muted">
          LangGraph StateGraph: intake → measure → score → segment → draft → gate. Zero LLM calls —
          every number is an exact comparison on the Olist rows. The in-browser scorer mirrors the
          Python engine exactly (12 shared test vectors), and the golden set of hand-verified sellers
          is evaluated on every test run.
        </p>
      </div>
    </div>
  );
}
