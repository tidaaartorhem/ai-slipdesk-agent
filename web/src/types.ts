export type Route = "ESCALATE" | "AT_RISK" | "WATCH" | "RELIABLE" | "UNSCORED";

export interface ScoreParts {
  late_rate: number;
  severity: number;
  breach: number;
  trend: number;
  worst: number;
}

export interface SellerRow {
  seller_id: string;
  seller_state: string;
  seller_city: string;
  orders: number;
  late_orders: number;
  late_rate: number;
  median_slip: number;
  late_median_slip: number;
  max_slip: number;
  worst_order_id: string;
  breach_orders: number;
  breach_rate: number;
  sep_late_rate: number;
  sep_n: number;
  ja_late_rate: number;
  ja_n: number;
  promised_median_days: number;
  p90_transit_days: number;
  recommended_promise_days: number;
  reset_lead_time: boolean;
  overdue_open: number;
  score: number;
  score_parts: ScoreParts;
  route: Route;
  action: string;
  instruction: string;
  draft: string;
  pending_approval: boolean;
}

export interface Summary {
  window: { start: string; end: string; label: string };
  snapshot: string;
  queue_size: number;
  scored_sellers: number;
  total_sellers_window: number;
  delivered_orders: number;
  late_orders: number;
  late_rate: number;
  by_route: Record<string, number>;
  reset_lead_time_count: number;
  overdue_open_in_queue: number;
  overdue_open_corpus: number;
  corpus: {
    delivered_orders: number;
    late_orders: number;
    late_rate: number;
    median_slip_days: number;
    ship_limit_breach_rate: number;
    monthly_late_rate_2017: Record<string, number>;
    window_late_rate_by_month: Record<string, number>;
  };
}

export interface SlipbookRule {
  id: string;
  name: string;
  detail: string;
  queue_count: number;
  corpus_note: string;
}

export interface Slipbook {
  rules: SlipbookRule[];
  segments: { escalate: number; at_risk: number; watch: number };
  min_orders: number;
  lead_reset_gap_days: number;
}

export interface TestVector {
  input: {
    n: number;
    late_orders: number;
    late_rate: number;
    late_median_slip: number;
    max_slip: number;
    breach_rate: number;
    sep_late_rate: number;
    sep_n: number;
    ja_late_rate: number;
    ja_n: number;
  };
  expected: {
    score: number;
    parts: ScoreParts;
    route: Route;
    action: string;
  };
}

export interface Stamp {
  repo: string;
  git_sha: string;
  built_utc: string;
  pipeline: string;
}

export interface SlipDeskData {
  summary: Summary;
  sellers: SellerRow[];
  slipbook: Slipbook;
  vectors: { vectors: TestVector[] };
  stamp: Stamp | null;
}
