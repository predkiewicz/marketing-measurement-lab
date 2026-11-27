# Which analysis for which decision

This repo runs every method at once, because it is a lab: each one is built, tested and connected to the others. A real marketing team does not need all of them for every decision. Most weekly work runs on a few clean numbers; experiments and models are for the few decisions that move a lot of money. Each method has a cost (time, money, lost revenue during a test, data it needs), so it should earn its place in the decisions it serves.

Two things are needed for every decision, at every size: clean data (duplicates removed, fraud flagged, consent-modelled counts) and numbers that reconcile with finance. Everything else depends on the decision.

## Decision first: what each one needs

| Decision | Who, how often | Needs | Can skip | In this repo |
|---|---|---|---|---|
| **Daily and weekly optimisation inside a channel**: bids, creatives, audiences, keywords | Channel managers, daily to weekly | Platform or last-click CPA and ROAS as trends within the channel; tracking QA (duplicate events, click injection); consent-modelled counts, so a change in consent is not read as a change in performance | Holdouts, response curves, lifetime value, geo tests. Within one channel, relative changes matter more than the true level | `fct_channel_roas`, `qa_duplicate_orders`, `qa_click_injection`, `fct_consent_impact` |
| **Budget and finance checks**: spend against plan, blended CAC against target, month-end reporting | Marketing lead with finance, monthly | Blended CAC; cost reconciled to invoices (ad spend plus commissions); revenue reconciled to the shop's orders; one shared definition of a customer | Attribution models, incrementality. Blended numbers need no credit split | `fct_blended_cac`, `assert_cac_reconciles`, `assert_revenue_reconciles` |
| **Cash flow and working capital**: can we afford to grow, how long is money tied up | CFO, quarterly or before scaling | Payback period on added customers; cash curve per channel (spend now, gross profit over months); gross margin | Response curves (unless the growth is large), geo tests | `fct_channel_cashflow`, `fct_customer_value` |
| **How channels influence each other**: which open journeys, which close them, does one channel feed another | Marketing lead and analytics, quarterly | Multi-touch attribution (position-based next to last click) and journey paths; holdouts that measure total sales, so effects on other channels are included | Lifetime value, response curves | `int_order_paths`, `fct_attribution`, `fct_channel_incrementality` |
| **Test, scale or stop a channel** | Marketing lead, quarterly | Incrementality with its interval (holdout); value of the added customers (180 days); marginal return from a response curve, for scaling; a clear goal (payback, CAC); fraud and consent corrections | Lifetime value (shown, but not decisive), geo power analysis (unless the next step is a test) | `fct_channel_decisions` |
| **Shifting budget from one channel to another** | Marketing lead, quarterly | Incrementality for both channels (what the money really buys); response curves (what the next euro buys, not the average one); equal-marginal-return allocation with caps | Attribution alone: it shows who was present, not what the money caused | `fct_response_curves`, `fct_budget_allocation` |
| **Budget planning for the next quarter or year** | Marketing lead with CFO, quarterly to yearly | All of the above, combined into a plan; sensitivity to the assumptions (margin, value horizon, curve uncertainty); goals the plan is checked against | Daily platform metrics | `fct_budget_scenario`, sensitivity table in [methodology.md](methodology.md) |
| **Business case for a new campaign or channel** | Marketing lead, CFO, before launch | Power analysis (how big and long a test must be to show the expected effect); a geo test or holdout with an honest interval; cost per extra customer against customer value; payback and lifetime value | Multi-touch attribution (a new channel has no history to attribute) | `geo_power.py`, `fct_geo_test`, `fct_geo_placebo`, `fct_channel_lifetime` |
| **Partner and affiliate terms**: commission rates, disputes, paying for new customers only | Performance team, at renewal or when anomalies show | Fraud checks (click injection); incrementality of the partner channel; commission on the partner's own last-click claim | Response curves, geo tests | `qa_click_injection`, `fct_channel_incrementality`, `fct_channel_cac` |
| **Setting CAC targets**: what can we pay for a customer | CFO with marketing, yearly | Customer value over a horizon finance accepts (180 days for cash, lifetime for strategy); gross margin; discount rate; how fast repeat buying fades | Attribution, response curves | `fct_customer_value`, `fct_ltv_decay`, `fct_channel_lifetime` |

Not in this repo: creative and landing-page A/B tests, and platform conversion-lift studies. They answer questions inside a channel and run in the ad platform or the website's testing tool.

## Method first: what each one costs

| Method | Answers | Costs | Refresh | Used by |
|---|---|---|---|---|
| Tracking QA: duplicates, click injection | Is the data telling the truth? | Little: SQL checks on data you already have | Daily, automated | Every decision |
| Reconciliation with finance | Do our numbers match the books? | Little, once definitions are agreed | Monthly | Budget checks, planning, CAC targets |
| Consent modelling | What does tracking miss, by channel? | Aggregate consent-banner counts per landing channel; some modelling error, which lands in direct traffic | Monthly, and after any banner change | Optimisation, attribution, any channel comparison |
| Blended CAC and ROAS | What do customers cost overall? | Little | Weekly to monthly | Finance checks, goal tracking |
| Last-click and multi-touch attribution | Who was present in the journey? | Clean journey data; says nothing about cause | Weekly | Optimisation, channel influence |
| Holdout tests (incrementality) | What would we lose without the channel? | Revenue lost in the holdout regions while the test runs; weeks of time; enough regions | Once or twice a year per major channel, and after big strategy changes | Test, scale or stop; budget shifts; partner terms |
| Budget-step tests (response curves) | What does the next euro buy? | Weeks of uneven spend across regions; wide intervals with few spend levels | Yearly, or before a large budget change | Scaling, budget shifts, planning |
| Customer value and payback (180 days) | When is the money back? | Six months of order history per cohort | Monthly | Test, scale or stop; cash flow; CAC targets |
| Lifetime value | What is a customer worth in the long run? | Many months of history; a projection with an assumption about how buying fades | Quarterly | CAC targets, strategy, business cases |
| Geo tests with placebo inference | Did this campaign cause the effect? | Campaign budget, weeks of time, and a power analysis before launch | Per campaign | Business cases, one-off campaigns |
| Power analysis | Is the test big and long enough to see the effect? | Little: history you already have | Before every test | Business cases, any planned holdout or geo test |
| Budget allocation and scenario | Where should the money go, and what does that do to the goals? | Needs incrementality, curves and customer value first | Quarterly | Budget shifts, planning |

## Where to start

- **A small shop with one or two paid channels:** tracking QA, reconciliation with finance, blended CAC and 180-day payback. That covers daily optimisation, finance checks and cash flow. Run one holdout on the biggest channel before scaling it.
- **A growing business with several paid channels:** add multi-touch attribution, consent modelling and a holdout per major channel each year. That is enough for test, scale or stop and for moving budget between channels.
- **A large budget, or a planned large change:** add response curves, budget allocation and planned geo tests with power analysis. They earn their cost when the money being moved is large compared with what the tests cost.

The question for any new analysis is the same: which decision will it change, and is that decision worth more than what the analysis costs?
