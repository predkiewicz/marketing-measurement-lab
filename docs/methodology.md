# Methodology and decisions

Every method in this repo is a choice, and every choice moves the numbers. This page records each one: what was decided, what else was on the table, why, what it changes, and how it is checked. Where a sensitivity is quoted, it comes from rerunning the build with a different setting (`dbt build --vars '{lookback_days: 7}'`).

## Data

### Synthetic, seeded data with planted problems

- **Decision:** generate all data with `scripts/generate_data.py` (Python standard library, fixed seed). Plant known problems and a known effect: duplicate purchase events, affiliate click injection, orders with no touchpoint, and an 8% lift in the geo test.
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

### Affiliate ROAS is always 10

- **Decision:** affiliate cost is a 10% commission on attributed revenue (`affiliate_fee`).
- **Impact:** ROAS is 1 / 0.10 = 10 by construction, under every model. It says nothing about whether affiliates drive sales. Only an incrementality test can answer that.

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
