# Agent rules

Rules for any coding agent working in this repo. `CLAUDE.md` imports this file; edit only here.

## Setup

```bash
source .venv/bin/activate   # or: python -m venv .venv && pip install -r requirements.txt
python scripts/generate_data.py
dbt build --profiles-dir .
```

## Done means

- `dbt build --profiles-dir .` ends with `ERROR=0`. Paste the `Done. PASS=...` line into the PR or summary.
- `dbt build --profiles-dir . --vars '{gross_margin: 0.75}'` is green too: only there do two SCALE channels compete for budget, so only there does `assert_allocation_optimal` really test something. Run it before the default build, so the tables end on default settings.
- `python scripts/geo_power.py` finishes without an assertion error (its self-check).
- A new test has been seen failing: break the logic it guards, run it, show the failure, restore. Say which break you used.
- README numbers match a fresh build. If a change moves them, update the tables.

## Data

- Synthetic only. Never add real company, customer, user or ad-account data, not even as an example.
- The generator is seeded; keep it deterministic. Planted problems (duplicate orders, click injection) stay, the QA models depend on them.
- Public repo: never add credentials, keys, tokens, login data, connection strings or anything personal. DuckDB is the only target; no cloud warehouse profiles.

## SQL

- Use dbt cross-database macros (`dbt.datediff`, `dbt.type_*`) instead of dialect functions, so the SQL stays portable.
- Settings go in `dbt_project.yml` vars, not as literals in models.
- One comment at the top of each model: what it is for, in plain words.
