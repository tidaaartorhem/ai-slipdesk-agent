import { useState } from "react";
import type { Route, SlipDeskData } from "../types";
import { SellerCard } from "./shared";

type RouteFilter = "all" | Route;
type ActionFilter = "all" | string;

const ROUTES: Route[] = ["ESCALATE", "AT_RISK", "WATCH", "RELIABLE"];

/** The seller queue: the top 100 Q3 2017 sellers by slip-risk score. */
export default function QueueView({ data }: { data: SlipDeskData }) {
  const [route, setRoute] = useState<RouteFilter>("all");
  const [action, setAction] = useState<ActionFilter>("all");
  const [query, setQuery] = useState("");

  const actions = [...new Set(data.sellers.map((s) => s.action))].sort();

  const shown = data.sellers.filter(
    (s) =>
      (route === "all" || s.route === route) &&
      (action === "all" || s.action === action) &&
      (query.trim() === "" ||
        (s.seller_id + " " + s.seller_city + " " + s.seller_state + " " + s.action)
          .toLowerCase()
          .includes(query.trim().toLowerCase())),
  );

  return (
    <div>
      <div className="card">
        <h2>Seller queue</h2>
        <p className="muted">
          {shown.length} of {data.sellers.length} queued sellers shown — the highest slip-risk sellers
          from {data.summary.scored_sellers} scored sellers in Q3 2017. ESCALATE means the promise is
          breaking now: chase the seller and reset the lead time. AT_RISK means the pattern is
          established — chase this week. Every chase draft needs human approval — nothing is sent
          until a person signs off.
        </p>
        <div className="filters">
          <div className="seg">
            {(["all", ...ROUTES] as const).map((f) => (
              <button key={f} className={route === f ? "active" : ""} onClick={() => setRoute(f)}>
                {f === "all"
                  ? `All (${data.sellers.length})`
                  : `${f.replace("_", " ")} (${data.sellers.filter((t) => t.route === f).length})`}
              </button>
            ))}
          </div>
          <div className="filter-row">
            <select value={action} onChange={(e) => setAction(e.target.value)} aria-label="Action filter">
              <option value="all">All actions</option>
              {actions.map((a) => (
                <option key={a} value={a}>
                  {a.replace(/_/g, " ")}
                </option>
              ))}
            </select>
            <input
              type="search"
              placeholder="Search sellers…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
      </div>
      {shown.map((s) => (
        <SellerCard key={s.seller_id} s={s} />
      ))}
    </div>
  );
}
