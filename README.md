# marketing-measurement-lab

Marketing measurement as tested code: attribution models, ROAS per channel, a geo test with its power analysis, and checks that catch broken or fraudulent tracking before it reaches a budget decision.

Runs on your laptop with DuckDB: no account, no cloud, no cost. All data is synthetic and seeded: there is no real company, customer or ad account behind any number here.

## What it answers

**Which channel earns its budget?** Same orders, two attribution models:

| Channel | ROAS, last click | ROAS, position-based |
|---|---:|---:|
| paid_social | 1.48 | 1.83 |
| display | 1.92 | 2.35 |
| paid_search | 1.41 | 1.07 |

In this data, journeys tend to start on social and display and end on search. Last click hands search the credit for demand that other channels created. Under position-based attribution (40% first touch, 40% last, 20% shared by the middle) search drops close to break-even. The budget decision flips with the model, which is why the model choice belongs in the open, not in a dashboard default.

**Is the data telling the truth?** The generator plants two problems that real tracking has:

| Check | What it finds | In this data |
|---|---|---|
| `qa_duplicate_orders` | Purchase tag firing twice; a naive sum overstates revenue | 29 orders |
| `qa_click_injection` | Affiliate clicks logged seconds before checkout, claiming commission for sales they did not drive | 48 clicks, excluded from attribution |

**Did the campaign cause it?** Attribution credits touchpoints; it cannot say what would have happened without them. A geo test can. Here a campaign ran for 28 days in 6 of Germany's 16 states (Bayern, Berlin, Bremen, Mecklenburg-Vorpommern, Saarland, Sachsen); the other 10 states are the control. The generator planted a true lift of 8%.

| Readout | Estimate | 95% interval |
|---|---:|---:|
| Lift in conversions | +8.1% | +4.2% to +12.1% |
| Incremental conversions | 724 | 390 to 1,047 |
| Cost per incremental conversion (EUR 81,984 spend) | EUR 113 | EUR 78 to EUR 210 |

`fct_geo_test` runs a difference-in-differences on the daily log ratio between treatment and control, each indexed to its own 56 days before the campaign, so the shared weekend dip and trend cancel out. The interval matters as much as the estimate: the same test supports a cost per incremental conversion anywhere between EUR 78 and EUR 210.

**How big must the test be?** `scripts/geo_power.py` answers that before any money is spent. It takes only the days before the campaign, picks 500 random sets of 6 treatment regions, adds a known lift and runs the same estimator:

| True lift | 14 days | 28 days |
|---|---:|---:|
| 0% (false alarms) | 5% | 6% |
| 4% | 34% | 53% |
| 6% | 60% | 77% |
| 8% | 82% | 93% |
| 10% | 93% | 99% |

With 6 regions, a 28-day test finds a 7% lift 80% of the time; a 14-day test needs 8%. A 4% effect would be missed about half the time, so a campaign expected to move conversions by a few percent needs more regions or more weeks, decided before the budget goes out.

## How it is checked

`dbt build` runs 9 models and 17 tests. Besides the usual `unique` / `not_null` tests, four tests guard the logic itself:

- `assert_weights_sum_to_one`: every order hands out exactly 100% credit under each model.
- `assert_revenue_reconciles`: attributed revenue equals order revenue. Models move credit between channels; they never create or lose money.
- `assert_geo_test_recovers_planted_lift`: the geo readout's interval contains the lift the generator planted.
- `assert_geo_placebo_shows_no_effect`: the same estimator on the two halves of the pre-campaign period finds nothing, so treatment and control moved together before the campaign.

A test only counts once it has been seen failing. Both were run against a deliberately broken model (first-touch weight 0.45 instead of 0.4): 850 orders failed the weights test and the reconciliation failed, as they should. Removing the deduplication makes `unique_stg_orders_order_id` fail on 29 orders. Swapping treatment and control makes the planted-lift test fail; letting the placebo read into the campaign period makes the placebo test fail. `geo_power.py` checks itself: with the interval removed (z = 0) its false-alarm check fails. GitHub Actions runs the generator, the power check and the full build on every push.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_data.py          # writes seeds/*.csv, same seed = same data
dbt build --profiles-dir .               # DuckDB file in target/lab.duckdb
python scripts/geo_power.py              # power table for the geo test
```

Look at the results:

```bash
python -c "import duckdb; print(duckdb.connect('target/lab.duckdb').sql('select * from fct_channel_roas'))"
```

## Layout

```
scripts/generate_data.py   synthetic touchpoints, orders, ad spend, geo test (stdlib only)
scripts/geo_power.py       simulation-based power for the geo test (stdlib only)
models/staging/            cleaned sources, duplicates removed
models/qa/                 tracking checks: duplicate orders, click injection
models/marts/              order paths, attribution weights, ROAS per channel, geo test readout
tests/                     logic tests that must fail when the logic breaks
```

Settings live in `dbt_project.yml` vars: lookback window (30 days), click-injection threshold (10 seconds), affiliate fee (10%), geo test start (1 June 2026) and interval (95%).

## Roadmap

- [ ] Indirect customer lifetime value: segments that look cheap on first order but bring valuable referrals
- [ ] Consent-aware counts: what share of conversions a consent-only setup sees, and how modelled conversions fill the gap
- [ ] Agent skills that work on this repo: a Tag Manager container audit (consent settings, duplicate pixels, dead triggers), a tracking-plan writer, a metric-definition review; each with its own test cases

## Working with AI agents

The repo is set up for coding agents (Claude Code, Gemini, Codex). `AGENTS.md` holds the rules and `CLAUDE.md` imports it, so there is one source and nothing to drift. The main rule is the one above: no change is done until `dbt build` is green, and a new test is not trusted until it has been seen failing.

## Author

Piotr Prędkiewicz, marketing and product analytics, Berlin. [predkiewicz.com](https://www.predkiewicz.com) · [LinkedIn](https://www.linkedin.com/in/predkiewicz)

MIT licence.
