# Decision memo: marketing budget, next quarter

To: VP Marketing, CFO · From: Marketing Analytics · Data: orders January to March 2026 with 180 days of repeat purchases, channel holdout tests 2025, regional campaign June 2026

*Fictional company, synthetic data. Every number comes from a fresh `dbt build` of this repo; `python scripts/report.py` prints them.*

## Our goals

- Every euro of acquisition is paid back by gross profit within 180 days.
- Blended CAC under EUR 26 (today: EUR 27.98).

## The decisions

| Channel | Decision | What we do next quarter |
|---|---|---|
| Paid social | **SCALE** | Move the paid search budget here in steps, and check the cost per customer at each step |
| Display | **TEST** | Repeat the holdout with more regions or more weeks before deciding |
| Affiliate | **TEST** | Pause in half the regions for 8 weeks; withhold commission on 48 orders with injected clicks |
| Paid search | **STOP** | Switch off in its current form; keep a small budget only where a test shows it adds customers |
| Regional campaign | **STOP** | Do not repeat in this form |

With the same budget, these decisions bring 12% more customers and 14% more gross profit, and blended CAC falls to EUR 24.91, below the goal.

![Return on the customers each channel added, after 180 days, worst to best case](decisions.svg)

## How we decide

For each channel, one number: the 180-day gross profit of the customers it **added**, per euro it cost (ROI). At 1.0 the channel has paid for itself within 180 days. Every measurement has an uncertainty range, so the rule only speaks when the range allows it:

- **SCALE** when ROI is at least 1.5, and at least 1.0 even in the pessimistic case.
- **STOP** when ROI is below 1.0 even in the optimistic case.
- **TEST** otherwise: the data cannot yet back a scale or a stop.

"Customers it added" is the key part. A channel can claim many customers who would have bought anyway. We measured this by switching each channel off in half the regions for 28 days and checking how much total sales dropped.

## Channel by channel

| Channel | New customers per 100 claimed | Cost per added customer | 180-day gross profit per customer | ROI: worst / expected / best | Paid back |
|---|---:|---:|---:|---|---:|
| Paid social | 92 | EUR 36.06 | EUR 60.55 | 1.39 / 1.68 / 1.83 | by day 30 |
| Display | 64 | EUR 41.01 | EUR 53.08 | 0.92 / 1.29 / 1.68 | by day 90 |
| Affiliate | 11 | EUR 58.29 | EUR 49.58 | 0.00 / 0.85 / 3.27 | no |
| Paid search | 38 | EUR 147.21 | EUR 56.09 | 0.29 / 0.38 / 0.48 | no |
| Regional campaign | n/a | EUR 113.24 | EUR 57.02 | 0.27 / 0.50 / 0.73 | no |

**Paid social: scale.** Its customers are almost all new (92 of 100), they come back more than those of any other paid channel, and the money is back within a month. Even the pessimistic case pays back. It opens most customer journeys, which last-click reports hide: there it costs about the same per customer as search (EUR 42).

**Paid search: stop.** In last-click reports it looks fine (CAC EUR 42), because it closes journeys that other channels started. But 62 of every 100 customers it claims would have found us anyway. Per customer it actually adds, it costs EUR 147, and even in the best case only half of that comes back within 180 days. Of every EUR 1,000 spent, EUR 619 is still lost after six months.

**Affiliate: test.** It looks like our cheapest channel (CAC EUR 6) and it lowers blended CAC on paper. But only about 11 of every 100 affiliate customers are new, and they come back the least. The holdout is too uncertain to stop on: the true value lies anywhere between losing everything and the best channel we have. We also found 48 injected clicks, logged seconds before checkout to claim commission; those orders are excluded from all numbers above.

**Display: test.** Probably profitable (expected ROI 1.29, paid back by day 90), but in the pessimistic case it does not pay back within 180 days. One sharper test decides between scale and keep.

**Regional campaign: stop.** It works: conversions in the campaign regions rose by 8% (4% to 12%). But each extra customer cost EUR 113, and a customer brings EUR 57 of gross profit in 180 days. Each EUR 81,984 run returns about EUR 41,000.

## What the plan does to the goals

| | Current | After the decisions |
|---|---:|---:|
| Budget | EUR 37,464 | EUR 37,464 |
| Customers | 1,339 | 1,504 |
| Blended CAC | EUR 27.98 | EUR 24.91 |
| 180-day gross profit | EUR 76,353 | EUR 86,783 |
| CAC goal (under EUR 26) | missed | met |

The plan assumes the budget moved to paid social buys customers 50% more expensively than today (EUR 54 instead of EUR 36), because the next euro in a channel is never as good as the average one. If it is twice as expensive, blended CAC lands at EUR 26.04 and just misses the goal. That is why social is scaled in steps, with the cost per added customer checked at each step.

## How sure we are

- **Paid search and the regional campaign:** STOP holds under every assumption we tried (gross margin 40% to 60%, 90 or 180 days of customer value).
- **Paid social:** SCALE holds at our 50% gross margin and 180-day horizon. At 40% margin, or with only 90 days of value, it drops to TEST: still profitable, but not by enough to scale with confidence.
- **Display:** becomes SCALE only at 60% margin.

The tracking is cleaned before any of this: 29 duplicate purchase events (2.2% of revenue overstated) are removed, and injected affiliate clicks get no credit.

## Decisions needed

| # | Decision | Recommendation | Owner |
|---|---|---|---|
| 1 | Stop paid search in its current form, move the budget to paid social | Yes, in monthly steps. Pause the next step if social's cost per added customer rises above EUR 54 (what the plan assumes); above EUR 61 the extra budget no longer pays back in 180 days | VP Marketing |
| 2 | Affiliate programme | Pause in half the regions for 8 weeks; withhold commission on the 48 flagged orders; renegotiate to pay only for new customers | Performance team |
| 3 | Display | Repeat the holdout with more regions or weeks, sized in advance with the power analysis | Analytics |
| 4 | Regional campaign | Do not repeat in this form | VP Marketing |
| 5 | Reporting | Report ROI on added customers next to last-click ROAS, and base budget decisions on it | VP Marketing, CFO |

How these numbers were produced and why each method was chosen: [methodology.md](methodology.md).
