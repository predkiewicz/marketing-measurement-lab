# Decision memo: Q2 marketing measurement review

To: VP Marketing, CFO · From: Marketing Analytics · Data: January to June 2026, channel holdout tests 2025

*Fictional company, synthetic data. Every number comes from a fresh `dbt build` of this repo; `python scripts/report.py` prints them.*

## The short version

1. **Do not cut social and display on last-click numbers.** They open most customer journeys. Last click undervalues them by more than 20%; paid search looks better than it is.
2. **Fix two tracking problems before the next budget round.** Duplicate purchase events overstate revenue by 2.2%, and one affiliate source claims commission with injected clicks.
3. **Paid search and affiliates mostly claim customers who would have come anyway.** Holdout tests show about 38% of paid search customers and about 11% of affiliate customers are new. Per added customer, paid search costs EUR 147 and affiliates EUR 58, not EUR 42 and EUR 6.
4. **The regional campaign works, but it is not yet clear that it pays.** It lifted conversions by about 8%. One extra customer costs between EUR 78 and EUR 210, against an average first order of EUR 60.

## 1. Channel budgets depend on the attribution model

| Channel | ROAS, last click | ROAS, position-based |
|---|---:|---:|
| Paid social | 1.48 | 1.83 |
| Display | 1.92 | 2.35 |
| Paid search | 1.41 | 1.07 |

Most journeys start on social or display and end on search. Last click gives search all the credit for demand the other channels created. Position-based attribution (40% first touch, 40% last, 20% for the touches in between) shares it out. Under that view, paid search is close to break-even.

Attribution shows who was present, not who caused the sale. Section 2 adds what the holdout tests found.

## 2. What a customer really costs

Each paid channel was switched off in half the regions for 28 days in 2025. The drop in total conversions shows what the channel adds; the rest of what it claims came back as organic or unattributed.

| Channel | New customers per 100 claimed | CAC, last click | CAC, per added customer |
|---|---:|---:|---:|
| Paid social | 92 (76 to 100) | EUR 41.65 | EUR 36.06 |
| Display | 64 (45 to 83) | EUR 31.55 | EUR 41.01 |
| Paid search | 38 (29 to 48) | EUR 42.04 | EUR 147.21 |
| Affiliate | 11 (0 to 43) | EUR 5.92 | EUR 58.29 |

Ranges are 95% intervals, capped at 0 and 100; the raw intervals are in the [methodology](methodology.md).

Affiliates make blended CAC look better: EUR 27.98 with them, EUR 29.77 without, if all their customers were really theirs. But only about 12 of their 103 customers are new. Without affiliates the business would save EUR 675 in commission, lose about 12 customers, and blended CAC would fall to EUR 27.71.

## 3. Two tracking problems distort the numbers

| Problem | Found | Effect |
|---|---|---|
| Purchase tag fires twice | 29 orders | Revenue overstated by EUR 1,806 (2.2%) in any report that sums the raw feed |
| Affiliate click injection | 48 clicks logged 2 to 8 seconds before checkout | EUR 2,912 of orders claimed; about EUR 291 in commission at the 10% rate |

Both are already corrected in the reported numbers: duplicates are removed, and injected clicks earn no credit. The open actions are a fix at the source (the tag) and a dispute with the affiliate network.

## 4. The regional campaign: a real effect with a wide cost range

The campaign ran for 28 days in 6 of 16 federal states. The other 10 states were the comparison group.

![Treatment and control regions, 7-day average](geo_test.svg)

| | Estimate | 95% interval |
|---|---:|---:|
| Lift in conversions | +8.1% | +4.2% to +12.1% |
| Extra conversions | 724 | 390 to 1,047 |
| Cost per extra conversion (EUR 81,984 spend) | EUR 113 | EUR 78 to EUR 210 |

The effect is real: even the low end of the interval is above zero, and the same method finds no effect in a period when nothing changed. The cost per extra customer is less certain. At EUR 113 it is about 1.9 average first orders, so the campaign pays back only if a customer orders about twice or more. This dataset cannot answer that yet; a lifetime value model is on the roadmap.

## Decisions needed

| # | Decision | Recommendation | Owner |
|---|---|---|---|
| 1 | Default attribution model in reporting | Position-based, with last click shown next to it | VP Marketing |
| 2 | Maximum cost per extra customer | Set from margin and repeat rate. Above EUR 210: scale the campaign. Between EUR 78 and 210: extend the test. Below EUR 78: stop. | CFO |
| 3 | Affiliate programme | Withhold commission on the 48 flagged orders. Renegotiate to pay only for new customers, or pause the programme in a few regions and confirm the holdout result. | Performance team |
| 4 | Paid search budget | Cut bids on terms where customers find the shop anyway (brand terms first) in a few regions, and measure the drop in total conversions before cutting nationally | Performance team |
| 5 | Display | Repeat the holdout with more regions or more weeks; the current test cannot say whether display is mostly new demand | Analytics |

How these numbers were produced and why each method was chosen: [methodology.md](methodology.md).
