# marketing-measurement-lab

Marketing measurement as tested code: attribution models, ROAS per channel, and checks that catch broken or fraudulent tracking before it reaches a budget decision.

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

## How it is checked

`dbt build` runs every model and 21 tests. Besides the usual `unique` / `not_null` tests, two tests guard the logic itself:

- `assert_weights_sum_to_one`: every order hands out exactly 100% credit under each model.
- `assert_revenue_reconciles`: attributed revenue equals order revenue. Models move credit between channels; they never create or lose money.

A test only counts once it has been seen failing. Both were run against a deliberately broken model (first-touch weight 0.45 instead of 0.4): 850 orders failed the weights test and the reconciliation failed, as they should. Removing the deduplication makes `unique_stg_orders_order_id` fail on 29 orders. GitHub Actions runs the full build on every push.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_data.py          # writes seeds/*.csv, same seed = same data
dbt build --profiles-dir .               # DuckDB file in target/lab.duckdb
```

Look at the results:

```bash
python -c "import duckdb; print(duckdb.connect('target/lab.duckdb').sql('select * from fct_channel_roas'))"
```

## Layout

```
scripts/generate_data.py   synthetic touchpoints, orders, ad spend (stdlib only)
models/staging/            cleaned sources, duplicates removed
models/qa/                 tracking checks: duplicate orders, click injection
models/marts/              order paths, attribution weights, ROAS per channel
tests/                     logic tests that must fail when the logic breaks
```

Settings live in `dbt_project.yml` vars: lookback window (30 days), click-injection threshold (10 seconds), affiliate fee (10%).

## Roadmap

- [ ] Indirect customer lifetime value: segments that look cheap on first order but bring valuable referrals
- [ ] Consent-aware counts: what share of conversions a consent-only setup sees, and how modelled conversions fill the gap
- [ ] Agent skills that work on this repo: a Tag Manager container audit (consent settings, duplicate pixels, dead triggers), a tracking-plan writer, a metric-definition review; each with its own test cases

## Working with AI agents

The repo is set up for coding agents (Claude Code, Gemini, Codex). `AGENTS.md` holds the rules and `CLAUDE.md` imports it, so there is one source and nothing to drift. The main rule is the one above: no change is done until `dbt build` is green, and a new test is not trusted until it has been seen failing.

## Author

Piotr Prędkiewicz, marketing and product analytics, Berlin. [predkiewicz.com](https://www.predkiewicz.com) · [LinkedIn](https://www.linkedin.com/in/predkiewicz)

MIT licence.
