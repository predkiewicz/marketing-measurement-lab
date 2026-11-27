# Methodology and decisions

Every method in this repo is a choice, and every choice moves the numbers. This page records each one: what was decided, what else was on the table, why, what it changes, and how it is checked. Where a sensitivity is quoted, it comes from rerunning the build with a different setting (`dbt build --vars '{lookback_days: 7}'`).

## Data

### Synthetic, seeded data with planted problems

- **Decision:** generate all data with `scripts/generate_data.py` (Python standard library, fixed seed). Plant known problems and known effects: duplicate purchase events, affiliate click injection, orders with no touchpoint, repeat purchases that depend on the acquisition channel, a known incrementality per paid channel, and an 8% lift in the geo test.
- **Alternatives:** a public dataset (the GA4 sample e-commerce data); anonymised real data.
- **Why:** with real data the true answer is unknown, so nobody can tell whether a method works. Planted problems give a ground truth: the QA models must find them and the geo readout must recover the 8%. A public repo also cannot hold real company data.
- **Impact:** the methods are validated against a known answer. The data is cleaner than reality. For example, the gap between injected clicks (2 to 8 seconds) and real clicks (at least 4.5 hours) is wider than it would be in practice.
- **Check:** the generator asserts it is deterministic and that the planted problems exist. Each new problem gets its own random stream, so adding one does not change the existing numbers.

### DuckDB only

- **Decision:** run everything on a local DuckDB file.
- **Alternatives:** BigQuery or Snowflake.
- **Why:** anyone can reproduce the results in minutes with no account, cost or credentials. A public repo must never hold login data.
- **Impact:** none on the results. The SQL uses dbt's cross-database macros, so it stays portable.

## Tracking QA

### Duplicate orders: keep the first event, report the rest

- **Decision:** `stg_orders` keeps one row per `order_id`, and `qa_duplicate_orders` lists every duplicate with the revenue it would overstate.
- **Alternatives:** drop duplicates silently; leave them in.
- **Why:** dropping them silently hides a broken tag that someone has to fix. Leaving them in overstates revenue.
- **Impact:** the raw feed sums to EUR 82,721 and the clean one to EUR 80,915, a difference of 2.2%.
- **Check:** `unique_stg_orders_order_id`. Remove the deduplication and it fails on 29 orders.

### Click injection: a time threshold, then exclude

- **Decision:** flag affiliate clicks logged less than 10 seconds before an order (`injection_threshold_s`). Flagged clicks are excluded from attribution, not deleted.
- **Alternatives:** keep them but give them less weight; use a model on click-to-order times.
- **Why:** nobody clicks an ad and completes checkout in a few seconds. A threshold is easy to explain to an affiliate network in a dispute. Excluding the clicks (instead of deleting them) keeps the evidence.
- **Impact:** any threshold from 9 seconds to about 4 hours finds exactly the 48 planted clicks. At 5 seconds only 18 are found. In real data the two groups overlap, so set the threshold from the distribution of click-to-order times and accept some missed fraud in return for fewer false accusations.
- **Check:** orders whose only touch was an injected click fall to `unattributed`, and the revenue reconciliation still holds.

## Attribution

### Position-based 40/20/40, shown next to last click

- **Decision:** credit 40% to the first touch, 40% to the last, and 20% shared by the touches in between. One touch gets 100%; two touches get 50/50. Always report last click next to it.
- **Alternatives:** linear, time decay, data-driven (Shapley or Markov).
- **Why:** journeys here have a clear opener (social, display) and a clear closer (search). Position-based credits both and is easy to explain. Data-driven models need more data and are hard to audit. Showing two models makes the dependence on the model visible instead of hiding it in a default.
- **Impact:** paid search ROAS is 1.41 under last click and 1.07 under position-based; paid social is 1.48 and 1.83.
- **Check:** `assert_weights_sum_to_one`. With the first-touch weight set to 0.45, 850 orders fail.

### 30-day lookback window

- **Decision:** only touchpoints up to 30 days before the order earn credit (`lookback_days`).
- **Alternatives:** 7 days (common ad-platform default), 90 days.
- **Why:** the window should cover the full journey. The longest journeys here are under 30 days.
- **Impact:** at 7 days, paid search position-based ROAS rises from 1.07 to 1.28 and paid social falls from 1.83 to 1.63. A short window cuts off the start of the journey, and the upper funnel loses credit. At 90 days nothing changes.

### Unattributed revenue stays visible

- **Decision:** orders with no eligible touchpoint keep one row with the channel `unattributed`.
- **Alternatives:** an inner join, which drops those orders.
- **Why:** an attribution table that loses revenue looks complete when it is not. Direct orders are a fact to report, not noise to filter out.
- **Impact:** 60 orders, EUR 3,621.
- **Check:** `assert_revenue_reconciles` compares attributed revenue with all orders. With an inner join it fails.

### Affiliate cost is the network's invoice

- **Decision:** affiliate cost is the 10% commission (`affiliate_fee`) on the orders the network claims by last click. It does not move with our attribution model.
- **Alternatives:** scale the commission with each model's credit (the first version did this).
- **Why:** the network invoices on its own last-click claim, whatever model we report. Scaling the cost with our model made affiliate ROAS exactly 10 under every model, which looked like a finding but was only arithmetic.
- **Impact:** affiliate ROAS is 10 under last click (1 / fee, by construction) and 9.04 under position-based. Neither says whether affiliates add customers; the holdout tests do.

## Incrementality and CAC

### One holdout test per paid channel

- **Decision:** switch each paid channel off in 8 of 16 regions for 28 days, after 56 days of history, one channel after another (2025). Measure the drop in *total* conversions with the same difference-in-differences estimator as the geo test.
- **Alternatives:** compare channel-attributed numbers before and after; marketing mix modelling; ghost ads or platform lift studies.
- **Why:** when a channel is off, its attributed conversions always vanish; the question is whether total conversions vanish with them or come back as organic and unattributed. Only the total answers that. Half of the regions as holdout gives more precision than the geo test's 6 of 16, because the effect on total conversions is small for small channels.
- **Impact:** incrementality = conversions lost in total / conversions the channel would have claimed. Paid social 0.92, display 0.64, paid search 0.38, affiliate 0.11.
- **Check:** `assert_incrementality_recovers_planted`: every interval contains the planted value. Assuming every attributed conversion is incremental makes it fail for all four channels.
- **Limit:** a holdout costs revenue while it runs (the incremental part of the channel is switched off). Affiliate's interval reaches below zero, which is impossible in reality and shows how hard a 9% channel is to measure: a sharper answer needs more regions or a longer test.

### Verdict line at 0.5

- **Decision:** a channel "mostly claims existing demand" when its whole interval is below 0.5, is "mostly incremental" when its whole interval is above, and is "inconclusive" otherwise (`incrementality_threshold`).
- **Why:** a verdict from the point estimate alone would call display incremental at 0.64, although its interval reaches down to 0.45. The rule only speaks when the test can.

### CAC: last click, position-based and incremental, side by side

- **Decision:** cost per customer three ways. Incremental CAC = cost / (position-based customers × measured incrementality). Every customer orders once in this data, so customers = orders.
- **Why:** each view answers a different question. Last click: what the platforms report. Position-based: who took part in the journey. Incremental: what the money actually bought.
- **Assumption:** incrementality measured in the 2025 holdouts still holds for the 2026 attribution data. If channel strategy changes (new bidding, new affiliate partners), the holdout has to be repeated.
- **Impact:** paid search costs EUR 42 per customer by last click and EUR 147 per added customer; affiliate EUR 6 and EUR 58.

### Blended CAC next to the views that explain it

- **Decision:** report blended CAC (all cost / all customers) together with paid-media-only, without-affiliate (as attributed and incremental) and fully incremental CAC.
- **Why:** blended CAC is the number finance sees, and a cheap channel lowers it even if it only claims existing customers. Removing affiliates "as attributed" raises blended CAC from EUR 27.98 to EUR 29.77; removing them in the incremental view lowers it to EUR 27.71. The difference is the commission paid for customers who were coming anyway.
- **Check:** `assert_cac_reconciles`: blended cost and customers match the books, the commission recomputed from the attribution table. Its first version read the commission from the model under test and stayed green when the commission was dropped; that is how the circular check was found.

## Customer value and payback

### 180-day gross profit, not first-order revenue

- **Decision:** value a customer as gross profit (revenue x `gross_margin`, 50%) from the first order plus repeat orders within `value_horizon_days` (180). Per channel, weight each customer by position-based credit.
- **Alternatives:** first-order ROAS; a predicted lifetime value (BG/NBD, Gamma-Gamma) over several years.
- **Why:** first orders are worth about the same everywhere (EUR 29 to 31 of gross profit); channels differ in who comes back. Revenue overstates what pays the bills, so gross profit. 180 days is long enough to see repeat buying and short enough to be measured, not predicted: no model assumption sits between the data and the budget decision.
- **Impact:** affiliate customers reach EUR 49.58 by day 180, paid social EUR 60.55. Over a longer horizon the gap grows.
- **Check:** `assert_value_reconciles` recomputes total value from the sources; `assert_value_never_decreases` guards the cumulative logic.

### Payback day and cash view

- **Decision:** payback is the first 30-day step at which a customer's cumulative gross profit covers the channel's incremental CAC. The cash view shows net cash per EUR 1,000 spent at each step, counting only added customers.
- **Why:** two channels with the same 180-day ROI can need very different amounts of cash in between. A channel that pays back in a month can be scaled from running revenue; one that needs six months has to be financed.
- **Impact:** paid social is back in the black by day 30, display by day 90. Paid search still has EUR 619 of every EUR 1,000 under water at day 180.
- **Check:** `assert_cashflow_matches_roi`: the cash line ends exactly where the ROI says.

## Decisions

### One number per channel: ROI on added customers

- **Decision:** ROI = 180-day gross profit of the customers a channel added / its cost. Added customers = position-based customers x measured incrementality. The regional campaign uses the geo test's incremental conversions, valued at the all-customer average.
- **Alternatives:** ROAS; CAC against a fixed target; contribution margin after a full year.
- **Why:** it combines the three things that decide whether money is well spent: does the channel add customers (incrementality), are they worth it (value), and how fast (horizon). ROAS misses the first two, CAC misses the second.
- **Assumption:** customers a channel adds are worth as much as the average customer it claims. If its added customers are better or worse than its claimed ones, the ROI moves with them.

### SCALE, TEST, STOP with the uncertainty built in

- **Decision:** SCALE when ROI >= 1.5 (`scale_min_roi`) and >= 1.0 in the worst case; STOP when ROI < 1.0 (`stop_max_roi`) even in the best case; TEST otherwise. Worst and best case come from the incrementality interval.
- **Alternatives:** decide on the point estimate; rank channels and cut the bottom.
- **Why:** on the point estimate, affiliate (ROI 0.85) would be stopped, although its interval reaches 3.27: a stop would rest on a test that cannot tell a losing channel from the best one. The rule says TEST instead and names what has to be measured. The 1.5 bar for scaling leaves room for diminishing returns.
- **Impact:** paid social SCALE; display and affiliate TEST; paid search and the regional campaign STOP.
- **Check:** `assert_every_paid_channel_decided`: no paid channel escapes a decision.

### Budget plan with diminishing returns

- **Decision:** STOP channels lose their cost and their *added* customers only. The freed budget goes to SCALE channels in proportion to their cost, at incremental CAC x 1.5 (`scale_cost_premium`). TEST channels stay as they are.
- **Alternatives:** reallocate at today's average CAC; fit response curves.
- **Why:** reallocating at today's CAC assumes the next euro works as well as the average one, which never holds. A response curve needs budget-step tests that this data does not have, so a flat premium stands in for it and is varied in the sensitivity check.
- **Impact:** same budget, 1,504 instead of 1,339 customers, blended CAC EUR 24.91 instead of EUR 27.98, 180-day gross profit +14%.
- **Check:** `assert_scenario_budget_neutral`. Its first version copied the total cost instead of adding up what it moved and could not fail; now it adds up the reallocated money, and a wrong allocation fails it.

### Which decisions survive other assumptions

Rerun with `dbt build --vars '{...}'`; ROI shown as expected value.

| Assumption | Paid social | Display | Affiliate | Paid search | Regional campaign | Plan: blended CAC |
|---|---|---|---|---|---|---:|
| As set: 50% margin, 180 days, premium 50% | SCALE 1.68 | TEST 1.29 | TEST 0.85 | STOP 0.38 | STOP 0.50 | EUR 24.91 |
| Gross margin 40% | TEST 1.34 | TEST 1.04 | TEST 0.68 | STOP 0.30 | STOP 0.40 | EUR 18.78 * |
| Gross margin 60% | SCALE 2.01 | SCALE 1.55 | TEST 1.02 | STOP 0.46 | STOP 0.60 | EUR 25.09 |
| 90 days of value | TEST 1.30 | TEST 1.04 | TEST 0.70 | STOP 0.31 | STOP 0.40 | EUR 18.78 * |
| Scale premium 100% | SCALE 1.68 | TEST 1.29 | TEST 0.85 | STOP 0.38 | STOP 0.50 | EUR 26.04 |

\* With no SCALE channel, the freed budget is saved instead of moved, so the plan spends less and blended CAC is not comparable with the other rows.

The STOP decisions hold everywhere. The SCALE decision for paid social needs at least 50% gross margin and the full 180 days of value. A 100% premium on scaled budget misses the CAC goal by EUR 0.04: the reason to scale in steps and watch the cost per added customer.

## Geo test

### Difference-in-differences on the log ratio of indexed series

- **Decision:** add up daily conversions per group, index each group to its own pre-campaign average, and take the log of the ratio between treatment and control. The lift is the change in the mean of that log ratio from before to during the campaign.
- **Alternatives:** compare raw totals; synthetic control; time-based regression (TBR).
- **Why:** indexing removes the size difference between the groups. The log ratio cancels what both groups share: the weekend dip, the trend, national news. The method is simple to explain and to recompute in Python, so the power analysis can use the same estimator.
- **Impact:** +8.1% estimated against 8% planted.
- **Check:** `assert_geo_test_recovers_planted_lift`. Swap treatment and control and it fails.

### A 95% interval, reported in money

- **Decision:** report lift, extra conversions and cost per extra conversion, each with a 95% interval.
- **Why:** a single cost per extra conversion of EUR 113 sounds precise. The interval of EUR 78 to EUR 210 is what a budget decision has to work with.
- **Limit:** the standard error treats days as independent. Real daily data is autocorrelated, so the interval would be too narrow. The placebo test below guards against that, and permutation inference or TBR is on the roadmap.

### Placebo test on the pre-campaign period

- **Decision:** run the same estimator on the two halves of the period before the campaign, where the true effect is zero.
- **Why:** if treatment and control were already drifting apart, the readout would mistake that drift for lift.
- **Check:** `assert_geo_placebo_shows_no_effect`. Let the placebo read into the campaign period and it fails.

### Random regions, sized by simulation

- **Decision:** treatment regions are a random draw of 6 of 16 states. Power comes from simulation: 500 random region sets, a known lift added, and the same estimator run.
- **Alternatives:** matched markets; a power formula.
- **Why:** a formula assumes things this data breaks (regions of very different sizes, shared shocks). Simulation uses the real pre-campaign series. A random draw is easy to defend; matched markets are more precise but harder to explain.
- **Impact:** with 6 regions, a 28-day test detects a 7% lift 80% of the time, and a 14-day test needs 8%. A 4% lift is missed about half the time.
- **Why 28 days of history, not 56:** the period before the campaign is 56 days long, and each simulated test needs history plus a fake test window of up to 28 days inside it. The real readout uses all 56 days, so it is slightly more precise than the power table suggests.
- **Check:** `geo_power.py` asserts a false-alarm rate of at most 10%. With the interval removed (z = 0), that check fails.

## Process

### A test counts only after it has been seen failing

- **Decision:** every logic test was run against a deliberately broken version before it was trusted. The README and the sections above name the break that was used.
- **Why:** a test that cannot fail proves nothing, and a green build can hide that. This rule exists because green checks can pass while testing nothing.
- **Check:** CI runs the generator, the power self-check, the full `dbt build` and the report on every push.
