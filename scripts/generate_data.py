"""Generate synthetic marketing data with known, planted problems.

Everything is fake and seeded, so every run produces the same CSVs.
Planted on purpose, so the checks in the dbt project have something to find:
  - duplicate purchase events (a tag firing twice)
  - click injection on one affiliate (click logged seconds before the order)
  - direct orders with no tracked touchpoint (typed URL, app, blocked tracking)
  - a geo test with a known effect: a campaign in 6 of 16 German states lifts conversions by 8%;
    regional series drift (autocorrelated deviations, own trends), as real regional data does
  - repeat purchases within 180 days that depend on the channel that brought the customer
    (REPEAT_RATE: coupon-driven affiliate customers come back least)
  - repeat buying beyond 180 days that decays by LATE_DECAY per month, observed only until
    OBSERVED_UNTIL (the analysis date), so each cohort is cut off at a different age
  - a consent banner: users who decline are invisible to tracking, at rates that differ by device,
    and device mix differs by channel (paid social is mostly iOS), so consent loss is uneven
  - budget-step tests with a known response curve per paid channel (CURVE_ELASTICITY)
  - channel holdout tests with known incrementality: part of what a channel claims would have
    arrived anyway as organic or unattributed (HOLDOUT_INCREMENTALITY)

Usage: python scripts/generate_data.py [--users N] [--seed S]
Writes CSVs to seeds/.
"""
import argparse
import csv
import math
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
GEO_AR = 0.9                       # a region's deviation today carries 90% into tomorrow (local weather, events, stock-outs)
GEO_DEVIATION_SD = 0.05            # typical size of that deviation
GEO_TREND_SD = 0.0005              # each region's own slow trend, per day


def generate_geo(seed: int) -> dict[str, list[dict]]:
    # own random stream, so adding the geo test does not change the attribution data
    rng = random.Random(seed + 1)
    codes = list(REGIONS)
    treated = set(rng.sample(codes, GEO_TREATED))
    regions = [{"region_code": c, "region_name": n, "population_m": p,
                "test_group": "treatment" if c in treated else "control"}
               for c, (n, p) in REGIONS.items()]

    # regional drift: an autocorrelated deviation (AR(1)) and an own trend per region. Without it, every
    # day is a fresh draw, and a readout that treats days as independent looks more precise than it is.
    trend = {c: rng.gauss(0, GEO_TREND_SD) for c in codes}
    deviation = {c: rng.gauss(0, GEO_DEVIATION_SD) for c in codes}
    innovation_sd = GEO_DEVIATION_SD * (1 - GEO_AR ** 2) ** 0.5

    daily = []
    for d in range(GEO_PRE_DAYS + GEO_TEST_DAYS):
        day = GEO_START + timedelta(days=d)
        # shared across regions: weekend dip, slow trend, national news / weather
        national = (0.85 if day.weekday() >= 5 else 1.0) * (1 + 0.002 * d) * rng.gauss(1, 0.04)
        in_test = d >= GEO_PRE_DAYS
        for c, (_, pop) in REGIONS.items():
            deviation[c] = GEO_AR * deviation[c] + rng.gauss(0, innovation_sd)
            mu = pop * GEO_CONV_PER_M * national * math.exp(deviation[c]) * (1 + trend[c] * d)
            if in_test and c in treated:
                mu *= 1 + GEO_LIFT
            daily.append({
                "geo_date": day.date().isoformat(),
                "region_code": c,
                "conversions": max(0, round(rng.gauss(mu, mu ** 0.5))),
                "campaign_spend_eur": round(pop * GEO_SPEND_PER_M, 2) if in_test and c in treated else 0.0,
            })
    return {"raw_geo_regions": regions, "raw_geo_daily": daily}


# Repeat purchases: expected number of further orders within REPEAT_DAYS of the first one, by the
# channel of the customer's first touch. Direct customers have no touch ('direct').
REPEAT_RATE = {
    "paid_social": 1.0, "display": 0.7, "paid_search": 0.8, "affiliate": 0.3,
    "email": 1.2, "organic": 1.1, "direct": 1.0,
}
REPEAT_DAYS = 180


def generate_repeats(tables: dict[str, list[dict]], seed: int) -> dict[str, list[dict]]:
    rng = random.Random(seed + 4)  # own random stream
    first_touch = {}
    for tp in sorted(tables["raw_touchpoints"], key=lambda t: t["touch_ts"]):
        first_touch.setdefault(tp["user_id"], tp["channel"])
    rows, seen = [], set()
    for o in tables["raw_orders"]:
        if o["order_id"] in seen:  # duplicate purchase event, not a second order
            continue
        seen.add(o["order_id"])
        rate = REPEAT_RATE[first_touch.get(o["user_id"], "direct")]
        # Poisson draw (Knuth), stdlib only
        n, p, limit = 0, rng.random(), math.exp(-rate)
        while p > limit:
            n += 1
            p *= rng.random()
        first = datetime.fromisoformat(o["order_ts"])
        for _ in range(n):
            rows.append({
                "repeat_order_id": f"r{len(rows) + 1:05d}",
                "first_order_id": o["order_id"],
                "user_id": o["user_id"],
                "order_ts": (first + timedelta(days=rng.uniform(1, REPEAT_DAYS))).isoformat(sep=" ", timespec="seconds"),
                "revenue_eur": round(rng.lognormvariate(4.0, 0.5), 2),
            })
    return {"raw_repeat_orders": rows}


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


# Repeat purchases after the first 180 days: the monthly rate of months 1-6 decays by LATE_DECAY per
# month from month 7 on, the same for every channel. Orders after OBSERVED_UNTIL have not happened yet.
LATE_DECAY = 0.85  # matches dbt var ltv_planted_decay
LATE_MONTHS = 36
OBSERVED_UNTIL = datetime(2026, 11, 27)  # matches dbt var observed_until


def generate_late_repeats(tables: dict[str, list[dict]], repeats: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed + 7)  # own random stream: the first 180 days stay exactly as they were
    first_touch = {}
    for tp in sorted(tables["raw_touchpoints"], key=lambda t: t["touch_ts"]):
        first_touch.setdefault(tp["user_id"], tp["channel"])
    rows, seen = [], set()
    for o in tables["raw_orders"]:
        if o["order_id"] in seen:
            continue
        seen.add(o["order_id"])
        level = REPEAT_RATE[first_touch.get(o["user_id"], "direct")] / 6  # orders per month, months 1-6
        first = datetime.fromisoformat(o["order_ts"])
        for month in range(7, LATE_MONTHS + 1):
            rate = level * LATE_DECAY ** (month - 6)
            n, p, limit = 0, rng.random(), math.exp(-rate)
            while p > limit:
                n += 1
                p *= rng.random()
            for _ in range(n):
                ts = first + timedelta(days=rng.uniform(max((month - 1) * 30, REPEAT_DAYS + 1), month * 30))  # never inside the 180-day value
                if ts <= OBSERVED_UNTIL:
                    rows.append({
                        "repeat_order_id": f"r{len(repeats) + len(rows) + 1:05d}",
                        "first_order_id": o["order_id"],
                        "user_id": o["user_id"],
                        "order_ts": ts.isoformat(sep=" ", timespec="seconds"),
                        "revenue_eur": round(rng.lognormvariate(4.0, 0.5), 2),
                    })
    return rows


# Consent: one banner decision per user, on the first visit. Rate by device; device mix by the channel
# the user arrived through. Declining users' touchpoints never reach the tracking; their orders still
# reach the shop's backend. The banner itself logs only aggregate counts per landing channel and device.
CONSENT_RATE = {"ios": 0.40, "android": 0.60, "desktop": 0.80}
DEVICE_MIX = {  # landing channel: (ios, android, desktop)
    "paid_social": (0.60, 0.30, 0.10), "display": (0.30, 0.30, 0.40), "paid_search": (0.20, 0.20, 0.60),
    "affiliate": (0.20, 0.20, 0.60), "email": (0.30, 0.20, 0.50), "organic": (0.25, 0.25, 0.50),
}


def generate_consent(tables: dict[str, list[dict]], seed: int) -> dict[str, list[dict]]:
    rng = random.Random(seed + 6)  # own random stream
    first_touch = {}
    for tp in sorted(tables["raw_touchpoints"], key=lambda t: (t["touch_ts"], t["touchpoint_id"])):
        first_touch.setdefault(tp["user_id"], tp["channel"])
    users, banner = [], {}
    for user_id, channel in sorted(first_touch.items()):
        device = rng.choices(list(CONSENT_RATE), DEVICE_MIX[channel])[0]
        consented = rng.random() < CONSENT_RATE[device]
        users.append({"user_id": user_id, "device": device, "consented": consented})
        key = (channel, device)
        views, accepted = banner.get(key, (0, 0))
        banner[key] = (views + 1, accepted + consented)
    banner_rows = [{"landing_channel": c, "device": d, "banner_views": v, "accepted": a}
                   for (c, d), (v, a) in sorted(banner.items())]
    # raw_consent is simulation only: it tells the lab which journeys a real setup would never see
    return {"raw_consent": users, "raw_consent_banner": banner_rows}


# Budget-step tests: for 8 weeks, each region gets a random spend level for one paid channel, from
# 0 (switched off) to 3x today's spend. Planted response curve: the customers a channel adds grow
# with spend as multiplier ** elasticity, so each extra euro buys fewer customers than the last.
CURVE_ELASTICITY = {"paid_social": 0.70, "display": 0.60, "paid_search": 0.40}  # matches dbt var curve_planted_elasticity
CURVE_LEVELS = [0, 0, 0, 0.5, 0.5, 0.75, 0.75, 1, 1, 1, 1.5, 1.5, 2, 2, 3, 3]  # one per region and week
CURVE_WEEKS = 8


def generate_budget_steps(seed: int) -> dict[str, list[dict]]:
    rng = random.Random(seed + 5)  # own random stream
    rows = []
    base = GEO_CONV_PER_M * 7  # conversions per million people and week without the channel's added customers
    for channel, elasticity in CURVE_ELASTICITY.items():
        added_today = base * HOLDOUT_SHARES[channel] * HOLDOUT_INCREMENTALITY[channel]
        for week in range(1, CURVE_WEEKS + 1):
            national = rng.gauss(1, 0.03)
            levels = CURVE_LEVELS[:]
            rng.shuffle(levels)
            for (code, (_, pop)), m in zip(REGIONS.items(), levels):
                mu = pop * national * (base * rng.gauss(1, 0.04) + added_today * m ** elasticity)
                rows.append({
                    "test_channel": channel,
                    "week": week,
                    "region_code": code,
                    "spend_multiplier": m,
                    "conversions": max(0, round(rng.gauss(mu, mu ** 0.5))),
                })
    return {"raw_budget_steps": rows}


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
    repeats = generate_repeats(tables, a.seed)
    assert repeats == generate_repeats(tables, a.seed)
    repeats["raw_repeat_orders"] += generate_late_repeats(tables, repeats["raw_repeat_orders"], a.seed)
    steps = generate_budget_steps(a.seed)
    assert steps == generate_budget_steps(a.seed)
    consent = generate_consent(tables, a.seed)
    assert consent == generate_consent(tables, a.seed)
    write(tables | geo | holdouts | repeats | steps | consent)
