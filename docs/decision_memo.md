# Decision memo: Q2 marketing measurement review

To: VP Marketing, CFO · From: Marketing Analytics · Data: January to June 2026

*Fictional company, synthetic data. Every number comes from a fresh `dbt build` of this repo; `python scripts/report.py` prints them.*

## The short version

1. **Do not cut social and display on last-click numbers.** They open most customer journeys. Last click undervalues them by more than 20%; paid search looks better than it is.
2. **Fix two tracking problems before the next budget round.** Duplicate purchase events overstate revenue by 2.2%, and one affiliate source claims commission with injected clicks.
3. **The regional campaign works, but it is not yet clear that it pays.** It lifted conversions by about 8%. One extra customer costs between EUR 78 and EUR 210, against an average first order of EUR 60.

## 1. Channel budgets depend on the attribution model

| Channel | ROAS, last click | ROAS, position-based |
|---|---:|---:|
| Paid social | 1.48 | 1.83 |
| Display | 1.92 | 2.35 |
| Paid search | 1.41 | 1.07 |

Most journeys start on social or display and end on search. Last click gives search all the credit for demand the other channels created. Position-based attribution (40% first touch, 40% last, 20% for the touches in between) shares it out. Under that view, paid search is close to break-even.

Attribution shows who was present, not who caused the sale. That is why I recommend a test before cutting search (see "Decisions needed").

## 2. Two tracking problems distort the numbers

| Problem | Found | Effect |
|---|---|---|
| Purchase tag fires twice | 29 orders | Revenue overstated by EUR 1,806 (2.2%) in any report that sums the raw feed |
| Affiliate click injection | 48 clicks logged 2 to 8 seconds before checkout | EUR 2,912 of orders claimed; about EUR 291 in commission at the 10% rate |

Both are already corrected in the reported numbers: duplicates are removed, and injected clicks earn no credit. The open actions are a fix at the source (the tag) and a dispute with the affiliate network.

## 3. The regional campaign: a real effect with a wide cost range

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
| 3 | Affiliate dispute | Withhold commission on the 48 flagged orders and raise it with the network | Performance team |
| 4 | Paid search incrementality | Run a regional holdout before cutting budget. With 6 regions, a 28-day test detects a 7% effect 80% of the time; a smaller expected effect needs more regions or more weeks. | Analytics |

How these numbers were produced and why each method was chosen: [methodology.md](methodology.md).
