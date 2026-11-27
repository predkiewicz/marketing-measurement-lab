"""Generate synthetic marketing data with known, planted problems.

Everything is fake and seeded, so every run produces the same CSVs.
Planted on purpose, so the checks in the dbt project have something to find:
  - duplicate purchase events (a tag firing twice)
  - click injection on one affiliate (click logged seconds before the order)
  - a geo test with a known effect: a campaign in 6 of 16 German states lifts conversions by 8%

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
    write(tables | geo)
