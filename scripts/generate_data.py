"""Generate synthetic marketing data with known, planted problems.

Everything is fake and seeded, so every run produces the same CSVs.
Planted on purpose, so the checks in the dbt project have something to find:
  - duplicate purchase events (a tag firing twice)
  - click injection on one affiliate (click logged seconds before the order)
  - direct orders with no tracked touchpoint (typed URL, app, blocked tracking)
  - a geo test with a known effect: a campaign in 6 of 16 German states lifts conversions by 8%
  - channel holdout tests with known incrementality: part of what a channel claims would have
    arrived anyway as organic or unattributed (HOLDOUT_INCREMENTALITY)

Usage: python scripts/generate_data.py [--users N] [--seed S]
Writes CSVs to seeds/.
"""
import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

CHANNELS = {  # channel: (share of touchpoints, cost per click EUR)
    "paid_search": (0.30, 3.50),
    "paid_social": (0.25, 2.80),
    "display": (0.15, 2.20),
    "affiliate": (0.10, 0.00),  # paid per order, see AFFILIATE_FEE
    "email": (0.10, 0.00),
    "organic": (0.10, 0.00),
}
FIRST_TOUCH = (0.10, 0.45, 0.30, 0.05, 0.05, 0.05)  # same channel order as CHANNELS
AFFILIATE_FEE = 0.10  # share of order revenue
DIRECT_ORDERS = 60    # orders with no tracked touchpoint
START = datetime(2026, 1, 1)
DAYS = 90
OUT = Path(__file__).resolve().parent.parent / "seeds"


def generate(users: int, seed: int) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    names, weights = zip(*[(c, w) for c, (w, _) in CHANNELS.items()])
    touchpoints, orders = [], []

    for u in range(1, users + 1):
        user_id = f"u{u:05d}"
        t = START + timedelta(seconds=rng.randrange(DAYS * 86400))
        for i in range(rng.randint(1, 6)):
            # journeys tend to start upper funnel (social, display) and end on search
            w = FIRST_TOUCH if i == 0 else weights
            touchpoints.append({
                "touchpoint_id": f"t{len(touchpoints) + 1:06d}",
                "user_id": user_id,
                "channel": rng.choices(names, w)[0],
                "touch_ts": t.isoformat(sep=" "),
            })
            t += timedelta(hours=rng.uniform(1, 96))

        if rng.random() < 0.25:  # converts
            order_ts = t + timedelta(hours=rng.uniform(0.1, 48))
            order = {
                "order_id": f"o{len(orders) + 1:05d}",
                "user_id": user_id,
                "order_ts": order_ts.isoformat(sep=" "),
                "revenue_eur": round(rng.lognormvariate(4.0, 0.5), 2),
            }
            orders.append(order)
            if rng.random() < 0.02:  # planted: purchase tag fires twice
                orders.append(dict(order))
            if rng.random() < 0.04:  # planted: injected affiliate click
                touchpoints.append({
                    "touchpoint_id": f"t{len(touchpoints) + 1:06d}",
                    "user_id": user_id,
                    "channel": "affiliate",
                    "touch_ts": (order_ts - timedelta(seconds=rng.randint(2, 8))).isoformat(sep=" "),
                })

    # planted: orders with no tracked touchpoint. Own random stream, so the data above stays unchanged.
    drng = random.Random(seed + 2)
    for i in range(1, DIRECT_ORDERS + 1):
        orders.append({
            "order_id": f"o{len(orders) + 1:05d}",
            "user_id": f"d{i:05d}",
            "order_ts": (START + timedelta(seconds=drng.randrange(DAYS * 86400))).isoformat(sep=" "),
            "revenue_eur": round(drng.lognormvariate(4.0, 0.5), 2),
        })

    spend = []
    clicks_per_day = {c: 0 for c in CHANNELS}
    for tp in touchpoints:
        clicks_per_day[tp["channel"]] += 1
    for d in range(DAYS):
        day = (START + timedelta(days=d)).date().isoformat()
        for channel, (_, cpc) in CHANNELS.items():
            if cpc:
                clicks = clicks_per_day[channel] / DAYS
                spend.append({"spend_date": day, "channel": channel,
                              "spend_eur": round(clicks * cpc * rng.uniform(0.8, 1.2), 2)})

    return {"raw_touchpoints": touchpoints, "raw_orders": orders, "raw_ad_spend": spend}


# Geo test: a campaign switched on in some German states, with a known effect.
REGIONS = {  # ISO 3166-2 code: (name, population in millions)
    "DE-BW": ("Baden-Württemberg", 11.1), "DE-BY": ("Bayern", 13.2), "DE-BE": ("Berlin", 3.8),
    "DE-BB": ("Brandenburg", 2.6), "DE-HB": ("Bremen", 0.7), "DE-HH": ("Hamburg", 1.9),
    "DE-HE": ("Hessen", 6.4), "DE-MV": ("Mecklenburg-Vorpommern", 1.6), "DE-NI": ("Niedersachsen", 8.1),
    "DE-NW": ("Nordrhein-Westfalen", 18.1), "DE-RP": ("Rheinland-Pfalz", 4.2), "DE-SL": ("Saarland", 1.0),
    "DE-SN": ("Sachsen", 4.1), "DE-ST": ("Sachsen-Anhalt", 2.2), "DE-SH": ("Schleswig-Holstein", 2.9),
    "DE-TH": ("Thüringen", 2.1),
}
GEO_START = datetime(2026, 4, 6)   # a Monday
GEO_PRE_DAYS, GEO_TEST_DAYS = 56, 28
GEO_TREATED = 6                    # regions that get the campaign
GEO_LIFT = 0.08                    # planted true effect on conversions (matches dbt var geo_planted_lift)
GEO_CONV_PER_M = 12                # baseline conversions per day per million people
GEO_SPEND_PER_M = 120              # campaign spend per day per million people, EUR


def generate_geo(seed: int) -> dict[str, list[dict]]:
    # own random stream, so adding the geo test does not change the attribution data
    rng = random.Random(seed + 1)
    codes = list(REGIONS)
    treated = set(rng.sample(codes, GEO_TREATED))
    regions = [{"region_code": c, "region_name": n, "population_m": p,
                "test_group": "treatment" if c in treated else "control"}
               for c, (n, p) in REGIONS.items()]

    daily = []
    for d in range(GEO_PRE_DAYS + GEO_TEST_DAYS):
        day = GEO_START + timedelta(days=d)
        # shared across regions: weekend dip, slow trend, national news / weather
        national = (0.85 if day.weekday() >= 5 else 1.0) * (1 + 0.002 * d) * rng.gauss(1, 0.04)
        in_test = d >= GEO_PRE_DAYS
        for c, (_, pop) in REGIONS.items():
            mu = pop * GEO_CONV_PER_M * national * rng.gauss(1, 0.05)
            if in_test and c in treated:
                mu *= 1 + GEO_LIFT
            daily.append({
                "geo_date": day.date().isoformat(),
                "region_code": c,
                "conversions": max(0, round(rng.gauss(mu, mu ** 0.5))),
                "campaign_spend_eur": round(pop * GEO_SPEND_PER_M, 2) if in_test and c in treated else 0.0,
            })
    return {"raw_geo_regions": regions, "raw_geo_daily": daily}


# Channel holdouts (2025): each paid channel switched off in half the regions for 28 days, one
# test after another. Planted truth: the share of a channel's attributed conversions that would
# NOT have happened without it. The rest would have arrived anyway as organic / unattributed.
HOLDOUT_INCREMENTALITY = {  # matches dbt var holdout_planted_incrementality
    "paid_social": 0.85, "display": 0.60, "paid_search": 0.45, "affiliate": 0.15,
}
HOLDOUT_SHARES = {  # share of a region's daily conversions attributed to each channel
    "paid_search": 0.28, "paid_social": 0.22, "display": 0.14, "affiliate": 0.09, "email": 0.09,
}  # the remaining 18% is organic / unattributed
HOLDOUT_START = datetime(2025, 1, 6)  # a Monday
HOLDOUT_PRE_DAYS, HOLDOUT_TEST_DAYS, HOLDOUT_REGIONS = 56, 28, 8


def generate_holdouts(seed: int) -> dict[str, list[dict]]:
    rng = random.Random(seed + 3)  # own random stream
    codes = list(REGIONS)
    rows = []
    for k, channel in enumerate(HOLDOUT_INCREMENTALITY):
        held_out = set(rng.sample(codes, HOLDOUT_REGIONS))
        start = HOLDOUT_START + timedelta(days=k * (HOLDOUT_PRE_DAYS + HOLDOUT_TEST_DAYS))
        for d in range(HOLDOUT_PRE_DAYS + HOLDOUT_TEST_DAYS):
            day = start + timedelta(days=d)
            national = (0.85 if day.weekday() >= 5 else 1.0) * (1 + 0.002 * d) * rng.gauss(1, 0.04)
            for c, (_, pop) in REGIONS.items():
                mu = pop * GEO_CONV_PER_M * national * rng.gauss(1, 0.05)
                mu_channel = mu * HOLDOUT_SHARES[channel]
                off = d >= HOLDOUT_PRE_DAYS and c in held_out
                if off:  # channel switched off: only the non-incremental part comes back as organic
                    mu -= mu_channel * HOLDOUT_INCREMENTALITY[channel]
                    mu_channel = 0.0
                channel_conv = max(0, round(rng.gauss(mu_channel, mu_channel ** 0.5))) if mu_channel else 0
                other = max(0, round(rng.gauss(mu - mu_channel, (mu - mu_channel) ** 0.5)))
                rows.append({
                    "test_channel": channel,
                    "holdout_date": day.date().isoformat(),
                    "region_code": c,
                    "is_holdout_region": c in held_out,
                    "is_test_period": d >= HOLDOUT_PRE_DAYS,
                    "conversions_total": channel_conv + other,
                    "conversions_channel": channel_conv,
                })
    return {"raw_holdout_daily": rows}


def write(tables: dict[str, list[dict]]) -> None:
    OUT.mkdir(exist_ok=True)
    for name, rows in tables.items():
        with open(OUT / f"{name}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        print(f"{name}: {len(rows)} rows")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--users", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    tables = generate(a.users, a.seed)
    # self-check: same seed, same data; planted problems are present
    assert tables == generate(a.users, a.seed)
    ids = [o["order_id"] for o in tables["raw_orders"]]
    assert len(ids) > len(set(ids)), "no duplicate orders planted"
    geo = generate_geo(a.seed)
    assert geo == generate_geo(a.seed)
    assert sum(r["test_group"] == "treatment" for r in geo["raw_geo_regions"]) == GEO_TREATED
    holdouts = generate_holdouts(a.seed)
    assert holdouts == generate_holdouts(a.seed)
    assert not any(r["conversions_channel"] for r in holdouts["raw_holdout_daily"]
                   if r["is_holdout_region"] and r["is_test_period"]), "channel still on in holdout"
    write(tables | geo | holdouts)
