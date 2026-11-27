"""Poison check: corrupt one raw feed at a time on a scratch copy, run `dbt build`, and show
which test stops it. The intake contracts in seeds/schema.yml must catch every corruption except
the two that are not corruptions (listed in EXPECTED_TO_PASS). Exits 1 if any other one slips
through. About 40 full builds: run it after changing seeds, contracts or column types.

    python scripts/poison_check.py
"""
import csv, io, shutil, subprocess, sys, re, pathlib, tempfile
REPO = pathlib.Path(__file__).resolve().parents[1]
WORK = pathlib.Path(tempfile.mkdtemp()) / "lab"
DBT = str(pathlib.Path(sys.executable).parent / "dbt")
# Not corruptions: duplicate order events are planted and removed by stg_orders (qa_duplicate_orders
# reports them); "yes" is a valid boolean spelling, DuckDB reads it as true.
EXPECTED_TO_PASS = {"dup_orders", "fmt_consent_yes"}
shutil.copytree(REPO, WORK, ignore=shutil.ignore_patterns(".venv", "target", "logs", ".git", "dbt_packages"))
CLEAN = {p.name: p.read_text() for p in (REPO / "seeds").glob("*.csv")}

def edit(table, fn):
    rows = list(csv.DictReader(io.StringIO(CLEAN[table + ".csv"])))
    fields = list(rows[0].keys())
    rows = fn(rows)
    out = io.StringIO(); w = csv.DictWriter(out, fields, lineterminator="\n"); w.writeheader(); w.writerows(rows)
    (WORK / "seeds" / (table + ".csv")).write_text(out.getvalue())

def dup(t): return lambda: edit(t, lambda r: r + [r[1]])
def setv(t, col, val, i=1):
    def f(r): r[i] = {**r[i], col: val}; return r
    return lambda: edit(t, f)
def add(t, row): return lambda: edit(t, lambda r: r + [row])

def repeat_before_first():
    orders = {r["order_id"]: r for r in csv.DictReader(io.StringIO(CLEAN["raw_orders.csv"]))}
    def f(r):
        o = orders[r[0]["first_order_id"]]["order_ts"][:10]
        import datetime as d
        r[0] = {**r[0], "order_ts": (d.date.fromisoformat(o) - d.timedelta(days=10)).isoformat() + " 12:00:00"}; return r
    edit("raw_repeat_orders", f)

def foreign_both():
    add("raw_geo_regions", {"region_code": "FR-IDF", "region_name": "Ile-de-France", "population_m": "12.3", "test_group": "control"})()
    add("raw_geo_daily", {"geo_date": "2026-04-06", "region_code": "FR-IDF", "conversions": "5000", "campaign_spend_eur": "0.0"})()

S = {
 "dup_orders": dup("raw_orders"),
 "dup_touchpoints": dup("raw_touchpoints"), "dup_repeat_orders": dup("raw_repeat_orders"),
 "dup_ad_spend": dup("raw_ad_spend"), "dup_geo_daily": dup("raw_geo_daily"),
 "dup_holdout_daily": dup("raw_holdout_daily"), "dup_budget_steps": dup("raw_budget_steps"), "dup_consent": dup("raw_consent"),
 "null_order_revenue": setv("raw_orders", "revenue_eur", ""), "null_consent_banner": setv("raw_consent_banner", "accepted", ""),
 "null_order_user_id": setv("raw_orders", "user_id", ""), "null_touchpoint_channel": setv("raw_touchpoints", "channel", ""),
 "null_ad_spend": setv("raw_ad_spend", "spend_eur", ""), "null_geo_conversions": setv("raw_geo_daily", "conversions", ""),
 "null_repeat_revenue": setv("raw_repeat_orders", "revenue_eur", ""),
 "fmt_timestamp_eu": setv("raw_orders", "order_ts", "06/03/2026 16:28"), "fmt_spend_date_bad": setv("raw_ad_spend", "spend_date", "2026-13-45"),
 "fmt_repeat_ts_bad": setv("raw_repeat_orders", "order_ts", "yesterday"), "fmt_revenue_text": setv("raw_orders", "revenue_eur", "EUR 50.00"),
 "fmt_geo_conv_float": setv("raw_geo_daily", "conversions", "136.7"),
 "fmt_consent_yes": setv("raw_consent", "consented", "yes"), "fmt_consent_maybe": setv("raw_consent", "consented", "maybe"),
 "oor_neg_repeat_revenue": setv("raw_repeat_orders", "revenue_eur", "-200.00"),
 "oor_mislabeled_channel_tp": setv("raw_touchpoints", "channel", "Paid_Social"),
 "oor_mislabeled_channel_spend": setv("raw_ad_spend", "channel", "tiktok"),
 "oor_consent_gt_100pct": setv("raw_consent_banner", "accepted", "200"),
 "oor_foreign_region_both": foreign_both,
 "oor_neg_geo_conversions_big": setv("raw_geo_daily", "conversions", "-500"),
 "oor_neg_geo_conversions_small": setv("raw_geo_daily", "conversions", "-5"),
 "oor_neg_order_revenue": setv("raw_orders", "revenue_eur", "-500.00"),
 "oor_neg_ad_spend": setv("raw_ad_spend", "spend_eur", "-5000.00"),
 "oor_order_years_ago": setv("raw_orders", "order_ts", "2019-01-01 12:00:00"),
 "oor_order_future": setv("raw_orders", "order_ts", "2030-06-15 12:00:00"),
 "oor_budget_step_neg_mult": setv("raw_budget_steps", "spend_multiplier", "-2"),
 "oor_foreign_region_daily": add("raw_geo_daily", {"geo_date": "2026-04-06", "region_code": "FR-IDF", "conversions": "100", "campaign_spend_eur": "99999.0"}),
 "oor_mislabeled_device_consent": setv("raw_consent", "device", "iPhone"),
 "oor_mislabeled_device_banner": setv("raw_consent_banner", "device", "iPhone"),
 "oor_repeat_before_first": repeat_before_first,
 "oor_holdout_channel_gt_total": setv("raw_holdout_daily", "conversions_channel", "9999"),
}
only = sys.argv[1:]
slipped = []
for name, poison in S.items():
    if only and not any(o in name for o in only): continue
    for n, t in CLEAN.items(): (WORK / "seeds" / n).write_text(t)
    poison()
    p = subprocess.run([DBT, "build", "--profiles-dir", "."], cwd=WORK, capture_output=True, text=True)
    out = re.sub(r"\x1b\[[0-9;]*m", "", p.stdout)
    fails = sorted(set(re.findall(r"(?:FAIL \d+|ERROR) +(?:\d+ )?([\w.]+)", out) + re.findall(r"(?:Failure|Database Error|Runtime Error|Compilation Error) in (?:test|seed|model) (\w+)", out)))
    done = (re.findall(r"Done\. (PASS=\d+ WARN=\d+ ERROR=\d+)", out) or ["no summary"])[0]
    verdict = "CAUGHT" if p.returncode else "PASSED"
    if verdict == "PASSED" and name not in EXPECTED_TO_PASS:
        slipped.append(name)
    print(f"{verdict:7} {name:30} {done:26} {', '.join(f for f in fails if f != 'in')[:120]}", flush=True)
shutil.rmtree(WORK.parent)
print("Slipped through:", ", ".join(slipped) if slipped else "none")
sys.exit(1 if slipped else 0)
