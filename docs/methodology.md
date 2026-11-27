# Methodology and decisions

Every method in this repo is a choice, and every choice moves the numbers. This page records each one: what was decided, what else was on the table, why, what it changes, and how it is checked. Where a sensitivity is quoted, it comes from rerunning the build with a different setting (`dbt build --vars '{lookback_days: 7}'`).

## Data

### Synthetic, seeded data with planted problems

- **Decision:** generate all data with `scripts/generate_data.py` (Python standard library, fixed seed). Plant known problems and known effects: duplicate purchase events, uneven consent loss, affiliate click injection, orders with no touchpoint, repeat purchases that depend on the acquisition channel and fade after six months, a known incrementality and a known response curve per paid channel, and an 8% lift in the geo test on regional data that drifts.
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

### Lifetime value beyond 180 days

- **Decision:** count repeat orders per customer by month since the first order, but in each month only customers observed that long by the analysis date (`observed_until`). Fit one decay for all channels after month 6: ln(orders per customer in month t / months-1-6 level) = (t - 6) x ln(decay), using months with at least 300 customers observed. Lifetime value = observed 180-day gross profit + the channel's own monthly level x the decayed months up to 36, discounted at 10% a year.
- **Alternatives:** a decay per channel; BG/NBD and Gamma-Gamma models; a fixed multiple of first-order value.
- **Why:** after 180 days there are only four usable months, and a fifth of the customers by month 10. Four decay rates from four noisy points each would be guesses; one shared rate uses all customers. What differs between channels, how often their customers buy, is already measured in the 180-day value. BG/NBD models need per-customer purchase histories over a longer window than this data has, and their assumptions are harder to explain to a CFO than one decay rate.
- **Impact:** decay 0.82 (0.74 to 0.91). Lifetime value EUR 63 (affiliate) to EUR 81 (paid social). No decision changes; affiliate's lifetime ROI is 1.09 against 0.85 over 180 days.
- **Check:** `assert_ltv_recovers_planted_decay`. Counting every customer in every month, without censoring, gives a decay of 0.62 and fails it: recent cohorts look like they stopped buying, when they have only had less time.
- **Limit:** the decay interval is wide (t value for 3 degrees of freedom), and the projection assumes the fade continues at the same rate for three years. That is why decisions stay on the 180-day goal and lifetime value is shown next to it, not instead of it.

## Decisions

### One number per channel: ROI on added customers

- **Decision:** ROI = 180-day gross profit of the customers a channel added / its cost. Added customers = position-based customers x measured incrementality. The regional campaign uses the geo test's incremental conversions, valued at the all-customer average.
- **Alternatives:** ROAS; CAC against a fixed target; contribution margin after a full year.
- **Why:** it combines the three things that decide whether money is well spent: does the channel add customers (incrementality), are they worth it (value), and how fast (horizon). ROAS misses the first two, CAC misses the second.
- **Assumption:** customers a channel adds are worth as much as the average customer it claims. If its added customers are better or worse than its claimed ones, the ROI moves with them.

### Response curves from budget-step tests

- **Decision:** for 8 weeks per paid channel, give each of the 16 regions a random spend level each week (0, 0.5, 0.75, 1, 1.5, 2 or 3 times today). Regions at 0 give that week's baseline; added customers per million people at each level = conversions minus baseline, averaged over the weeks. Fit `added = today x multiplier ^ elasticity` by regressing ln(added) on ln(multiplier).
- **Alternatives:** a flat cost premium on scaled budget (the previous version: +50%); a saturating Hill curve with adstock, as in marketing mix models; reading curves off ad-platform forecasts.
- **Why:** a flat premium is a guess that cannot be tested and says nothing about where to stop. A curve fitted to real budget steps can. The power curve has two parameters, is linear on logs and fits in plain SQL. A Hill curve also models a ceiling, but six spend levels cannot pin down three parameters. The power curve never fully saturates, so the plan never goes beyond the highest level tested (`curve_max_multiplier`, 3x).
- **Impact:** elasticities 0.68 (paid social), 0.57 (display), 0.28 (paid search). On this curve, marginal ROI = elasticity x average ROI, and the next euro stops paying back at today x (elasticity x ROI) ^ (1 / (1 - elasticity)): 1.48x today for paid social, 0.49x for display.
- **Check:** `assert_curves_recover_planted`: every interval contains the planted elasticity. Fitting on raw conversions without the baseline fails it for all 3 channels.
- **Limit:** with 6 levels and 4 degrees of freedom (`curve_ci_t` = 2.776), the intervals are wide. For paid social, the profitable spend ranges from 0.51x (elasticity 0.40) to the 3x cap (elasticity 0.96). More weeks or regions narrow it; until then, scaling happens in steps.

### SCALE, TEST, STOP with the uncertainty built in

- **Decision:** SCALE when the next euro still pays back (marginal ROI >= 1) and the average ROI is >= 1 even in the worst case; STOP when ROI < 1.0 (`stop_max_roi`) even in the best case; TEST otherwise. Worst and best case come from the incrementality interval. Channels without a response curve (affiliate is paid by commission, the regional campaign ran once) cannot be scaled on this evidence.
- **Alternatives:** decide on the point estimate; rank channels and cut the bottom; a fixed ROI bar for scaling (the previous version: 1.5).
- **Why:** on the point estimate, affiliate (ROI 0.85) would be stopped, although its interval reaches 3.27: a stop would rest on a test that cannot tell a losing channel from the best one. The rule says TEST instead and names what has to be measured. For scaling, average ROI answers the wrong question: display averages 1.29, but its last euros return 0.74. The curve answers the right one: does the next euro pay back?
- **Limit:** marginal ROI uses the elasticity's point estimate. At the low end of its interval, paid social's next euro would return 0.66. The step-wise plan is the answer to that uncertainty.
- **Impact:** paid social SCALE; display and affiliate TEST; paid search and the regional campaign STOP.
- **Check:** `assert_every_paid_channel_decided`: no paid channel escapes a decision.

### Budget plan: scale only as far as the next euro pays back

- **Decision:** STOP channels lose their cost and their *added* customers only. TEST channels stay as they are. The freed budget goes to the SCALE channels; added customers follow each channel's curve. Budget that no channel can use profitably is not spent.
- **Alternatives:** spend the whole freed budget at a flat premium (an earlier version); spend it all, whatever the return.
- **Why:** money a channel cannot turn into profit is better not spent.
- **Impact:** budget EUR 30,475 instead of EUR 37,464, 1,368 instead of 1,339 customers, blended CAC EUR 22.27, profit after marketing EUR 48,070 instead of EUR 38,889. The earlier flat-premium plan spent the full budget and promised 1,504 customers and EUR 49,318 profit after marketing: 136 customers that the curve says the extra money cannot buy.
- **Check:** `assert_scenario_budget_neutral`: new budget = old budget from the books - freed + allocated. A plan that forgets the allocation fails it. Its first version copied the total cost instead of adding up what it moved and could not fail.

### Allocation across SCALE channels: equal marginal ROI

- **Decision:** split the freed budget so that the next euro earns the same in every funded channel. On the power curve, a target marginal ROI fixes each channel's spend: today x (elasticity x ROI / target) ^ (1 / (1 - elasticity)), kept between today's spend and the profitable spend. `fct_budget_allocation` searches 4,000 targets between 1 and the best marginal ROI today and takes the lowest one whose spend fits the budget.
- **Alternatives:** split in proportion to today's cost (the previous version); give everything to the channel with the best average ROI; a solver.
- **Why:** as long as one channel's next euro earns more than another's, moving a euro raises profit, so the best split is where they are equal. A split by cost ignores the curves; "best average ROI first" ignores that the best channel gets worse as it grows. A grid in plain SQL needs no solver, and its error (EUR 7 left over at 75% margin) is far below the uncertainty of the curves.
- **Impact:** with the default data, paid social is the only SCALE channel, so both splits give the same plan. At 75% gross margin, display is SCALE too: the split by cost fills display to its cap (EUR 2,026), gives social EUR 9,269 and leaves EUR 2,832 unspent, for EUR 88,458 profit after marketing. The equal-marginal split gives social EUR 14,120 and display nothing, because display's next euro (1.10) never beats social's (still 1.37 after the extra budget): EUR 90,356, about EUR 1,900 more from the same money.
- **Check:** `assert_allocation_optimal` checks the conditions of an optimum on the result. CI also builds at 75% margin, where two channels compete; there the previous split fails it.
- **Limit:** the allocation is only as good as the curves. With their wide intervals, the split is a starting point for the step-wise plan, not a final budget.

### Which decisions survive other assumptions

Rerun with `dbt build --vars '{...}'`; ROI shown as expected value, profitable spend for paid social in brackets.

| Assumption | Paid social | Display | Affiliate | Paid search | Regional campaign | Plan: profit after marketing |
|---|---|---|---|---|---|---:|
| As set: 50% margin, 180 days | SCALE 1.68 (1.48x) | TEST 1.29 | TEST 0.85 | STOP 0.38 | STOP 0.50 | EUR 48,070 (now EUR 38,889) |
| Gross margin 40% | TEST 1.34 | TEST 1.04 | TEST 0.68 | STOP 0.30 | STOP 0.40 | EUR 33,437 (now EUR 23,618) |
| Gross margin 60% | SCALE 2.01 (2.60x) | TEST 1.55 | TEST 1.02 | STOP 0.46 | STOP 0.60 | EUR 64,792 (now EUR 54,159) |
| 90 days of value | TEST 1.30 | TEST 1.04 | TEST 0.70 | STOP 0.31 | STOP 0.40 | EUR 32,629 (now EUR 22,818) |

The STOP decisions hold everywhere, and the plan adds EUR 9,000 to 11,000 of profit after marketing under every assumption. Paid social's SCALE needs at least 50% gross margin and the full 180 days of value; at 40% margin or 90 days, its next euro no longer pays back. Display's last euros do not pay back under any of these assumptions (marginal ROI 0.59 to 0.88), even at 60% margin, where its average ROI reaches 1.55.

## Consent

### Simulate uneven consent loss

- **Decision:** one banner decision per user at the first visit, with consent rates by device (iOS 40%, Android 60%, desktop 80%) and device mix by landing channel (paid social 60% iOS). Declining users' touchpoints never reach tracking; their orders still reach the backend.
- **Why:** consent loss is not a flat haircut. If it were, every channel would shrink by the same share and decisions would not change. Because it follows device, and device follows channel, it hits paid social hardest.
- **Impact:** consent rates by landing channel from 49% (paid social) to 68% (paid search, email).

### Model it back by weighting observed journeys

- **Decision:** weight each consented order by 1 / consent rate of the channel its journey started from, measured from the banner's aggregate counts per landing channel. Unconsented orders are pulled back out of `unattributed`.
- **Alternatives:** scale each channel by one overall consent rate; scale each channel by its own landing rate regardless of the journey; rely on an ad platform's or analytics tool's modelled conversions.
- **Why:** a user decides once, at the first visit, so the channel of that visit decides whether the whole journey is seen. Weighting the journey (inverse probability weighting) follows that mechanism. Banner counts are aggregate, so the model needs no user data from people who declined. Platform models are black boxes and differ per platform.
- **Impact:** consent-only data understates every channel by 34% to 44%; modelled counts are within 7%. Paid social's decision is SCALE on true and modelled data, TEST on consent-only data.
- **Check:** `assert_consent_model_recovers_truth`. One overall consent rate instead of one per landing channel fails it for display (+11%) and affiliate (+13%).
- **Limit:** the modelled counts run 4% to 7% high here, because buyers' consent rates differ by chance from all visitors' (display 68% against 64%). These errors pile up in the leftover: modelled direct orders fall from 60 to 6. Direct traffic is the least reliable number in a consent-modelled report.
- **Why experiments matter here:** holdout, budget-step and geo tests count backend orders, so consent does not touch them. The decisions rest on them for incrementality and curves; consent modelling only has to get the attributed customer counts right.

## Geo test

### Regional data that drifts

- **Decision:** each region's daily conversions carry an autocorrelated deviation (90% of today's deviation carries into tomorrow, typical size 5%) and a slow trend of its own, on top of the national pattern.
- **Why:** an earlier version drew every region-day independently. On such data the textbook interval works, so the lab could not show where it fails. Real regional series drift: local weather, events, stock-outs and regional promotions last for days.
- **Impact:** the textbook standard error stays at 0.019 while the real noise of the estimator is 0.030.

### Difference-in-differences on the log ratio of indexed series

- **Decision:** add up daily conversions per group, index each group to its own pre-campaign average, and take the log of the ratio between treatment and control. The lift is the change in the mean of that log ratio from before to during the campaign.
- **Alternatives:** compare raw totals; synthetic control; time-based regression (TBR).
- **Why:** indexing removes the size difference between the groups. The log ratio cancels what both groups share: the weekend dip, the trend, national news. The method is simple to explain and to recompute in Python, so the power analysis can use the same estimator.
- **Impact:** +7.9% estimated against 8% planted.
- **Check:** `assert_geo_test_recovers_planted_lift`. Swap treatment and control and it fails.

### Interval and p-value from placebo sets, not from independent days

- **Decision:** run the same estimator on all 8,008 sets of 6 of the 16 regions, on the 56 days before the campaign (28 as baseline, 28 as a fake campaign), where the true effect is zero (`fct_geo_placebo`). The readout's interval is its estimate plus or minus 1.96 times the spread of those placebo estimates; its p-value is the share of placebo sets with an effect at least as large.
- **Alternatives:** the textbook standard error (the previous version); autocorrelation-robust (Newey-West) standard errors; time-based regression; synthetic control.
- **Why:** the textbook standard error treats days as independent; with drift they are not, and it is about a third too small. Placebo sets need no assumption about how the noise behaves: they use the real series, drift included, and every region takes part. Newey-West needs a choice of lag and still assumes a model of the noise. TBR and synthetic control are stronger with fewer regions, but harder to explain and to recompute in SQL.
- **Impact:** lift +7.9% with interval +1.8% to +14.4% (independent days: +4.0% to +12.0%), p = 0.005. Cost per extra conversion EUR 113, interval EUR 66 to EUR 463 (previously reported as EUR 78 to EUR 210 on data without drift). The regional campaign stays STOP: its ROI is 0.12 / 0.50 / 0.86.
- **Check:** `assert_geo_interval_calibrated`: applied to the placebo sets, the readout's interval may call at most 7% significant. Back on the independent-days interval, it calls about 20% and the test fails.
- **Limit:** the placebo sets use 28 days of baseline, the real readout 56, so the interval is slightly conservative. The placebo distribution is computed from the same 16 regions in the same weeks; a structural change after the baseline period would not show in it.

### Placebo test on the pre-campaign period

- **Decision:** run the same estimator on the two halves of the period before the campaign, where the true effect is zero, judged with the placebo standard error.
- **Why:** if treatment and control were already drifting apart, the readout would mistake that drift for lift.
- **Check:** `assert_geo_placebo_shows_no_effect`. Let the placebo read into the campaign period and it fails.

### Random regions, sized by simulation

- **Decision:** treatment regions are a random draw of 6 of 16 states. Power comes from simulation on the pre-campaign series: the bar for significance from half of the 8,008 placebo sets, the false-alarm rate checked on the other half, then 500 random region sets with a known lift added.
- **Alternatives:** matched markets; a power formula.
- **Why:** a formula assumes things this data breaks (regions of very different sizes, shared shocks, drift). A random draw is easy to defend; matched markets are more precise but harder to explain.
- **Impact:** with 6 regions, a 28-day test detects a 10% lift 80% of the time, and a 14-day test needs 11%. The planted 8% is found 71% of the time. Judged by the independent-days interval, the same simulation would have promised 7%, at a false-alarm rate of 20%.
- **Why 28 days of history, not 56:** the period before the campaign is 56 days long, and each simulated test needs history plus a fake test window of up to 28 days inside it.
- **Check:** `geo_power.py` asserts at most 7% false alarms on the placebo sets it was not calibrated on. Deciding significance with the independent-days interval instead fails it (15% at 14 days, 20% at 28).

## Process

### A test counts only after it has been seen failing

- **Decision:** every logic test was run against a deliberately broken version before it was trusted. The README and the sections above name the break that was used.
- **Why:** a test that cannot fail proves nothing, and a green build can hide that. This rule exists because green checks can pass while testing nothing.
- **Check:** CI runs the generator, the power self-check, the full `dbt build` and the report on every push.
