# SlipDesk — the supplier lead-time slip desk

**Live demo:** https://ai-slipdesk-agent.web.app
**Repo:** https://github.com/tidaaartorhem/ai-slipdesk-agent

A marketplace promises every customer a delivery date. The seller sets that promise — and
then slips. The buyer finds out when the parcel doesn't arrive; the ops team finds out when
the buyer complains. Nobody watches which sellers chronically break the promise versus had one
bad week, and nobody re-sets the promise when a seller's real lead time has drifted 16 days
past what they advertise.

SlipDesk is the slip desk for Meridian Marketplace, a fictional online marketplace operator.
A LangGraph pipeline (intake → measure → score → segment → draft → gate) scores every seller
on promise-vs-actual delivery for the Q3 2017 replay, queues the sellers to chase, and drafts
the chase note — including a recommended lead-time reset where the seller's own p90 transit
proves the promise unkeepable. Every action is a human-gated draft. Nothing is sent.

## What it found (Q3 2017, as of 2017-10-31)

- **12,215 delivered orders, 412 late (3.4%)**, across **974 sellers**; **456 sellers** scored
  (≥ 5 delivered orders). The web queue is the top 100 by score.
- **1 ESCALATE, 22 AT_RISK, 119 WATCH, 314 RELIABLE.** The single escalation: a seller with
  6 orders, 4 of them late (66.7%), median 14.5 days late, 83.3% of items shipped after the
  shipping-limit date — score 67.2.
- **25 sellers in the queue need their promised lead time reset** — their p90 actual transit
  beats their current promise by 5 days or more. The worst: a seller promising 26 days whose
  p90 transit is 48 days.
- **224 orders were still past their promised date and undelivered as of Oct 31**, across 148
  sellers; 66 of those sit with sellers in the queue.
- The late rate rose through the quarter — Jul 2.8%, Aug 2.9%, Sep 4.4% — which is why the
  score has a trend part. The full corpus tells the same story at larger scale: **6,534 of
  96,470 delivered orders late (6.77%)**, median slip −12 days (promises are padded — most
  orders arrive early), and the November 2017 late rate hit 12.4%.
- The tail matters more than the rate: one seller with 76 orders was late only 2.6% of the
  time — but one order arrived **109 days** late, and its median late slip was 58 days. It
  scores 28.4 (WATCH) on severity and worst-slip alone.

## How it works

Slip is `delivered_customer_date − estimated_delivery_date`, in days. Score 0–100, five
disclosed parts, no LLM calls:

| Part | Rule | Max |
| --- | --- | --- |
| Late rate | late share of delivered orders × 100 × 0.45 | 45 |
| Severity | median slip among late orders, capped at 15 days | 15 |
| Ship-limit breach | share of items handed to the carrier after the shipping-limit date × 100 × 0.20 | 20 |
| September trend | Sep late rate minus Jul–Aug late rate, in points, floored at 0, capped at 10; needs ≥ 2 orders on each side | 10 |
| Worst slip | min(10, max(0, worst slip − 7) / 2) — a single catastrophic slip is worth a look | 10 |

Segments: score ≥ 45 ESCALATE; ≥ 30 AT_RISK; ≥ 12 WATCH; otherwise RELIABLE. Sellers with
fewer than 5 delivered orders are UNSCORED. One recommended action per seller, highest-priority
signal first: RESET LEAD TIME → CHASE OVERDUE ORDERS → FIX SHIP-BY DISCIPLINE → CHASE AND COACH
→ CHECK SEPTEMBER CAPACITY → REVIEW THE CATASTROPHIC SLIP → MONITOR → NO ACTION.

The UI has four tabs: the seller queue (filter by segment, action, or search), the slipbook
(all five rules with queue and corpus counts), paste-a-seller (the same scoring runs in the
browser via the TypeScript mirror), and methodology.

## Data

Real data only: the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(Kaggle, CC BY 4.0), via the zero-auth mirror at
`github.com/olist/work-at-olist-data` — 99,441 orders, 112,650 item rows, 3,095 sellers.
The desk replays Q3 2017 purchases with the snapshot as of 2017-10-31. Meridian Marketplace is
fictional; the Olist rows are real. The source CSVs are not committed — `scripts/fetch_olist.py`
downloads them (or reuses a sibling checkout's cache) and derives the committed
`data/raw/*.json` (queue, corpus stats, scoring config, golden set, test vectors).

## Evaluation

- **Golden set:** 6 real sellers whose numbers were verified against the raw Olist rows (the
  top escalation, the 109-day-slip seller, the 261-order seller, and three more) plus 5
  hand-computed edge cases (all-on-time = 0, single late order = 7.5, half-late = 49.0,
  under-5-orders = UNSCORED at 51.5, trend guard = 20.5). Eval accuracy 1.000.
- **Python/TS contract:** 12 shared test vectors in `data/test-vectors.json`; the TypeScript
  mirror reproduces the Python engine's score, parts, route, and action on all 12 — including
  a Python-compatible round-half-even so 2.25 scores 2.2, not 2.3.
- **Tests:** 18/18 pytest + 23/23 vitest green.

## Run it

```bash
PYTHONNOUSERSITE=0 python3 scripts/fetch_olist.py   # rebuild data/raw/*.json from Olist
PYTHONNOUSERSITE=0 python3 -m pytest tests/ -q      # 18 passed
cd web && npm install && npm test                    # 23 passed
npm run build                                        # tsc + pipeline + vite build
```

(`PYTHONNOUSERSITE=0` is needed because this VM sets `PYTHONNOUSERSITE=1`; pytest and
langgraph live in the user site-packages. The graph falls back to the same nodes run
sequentially when langgraph is not importable.)
