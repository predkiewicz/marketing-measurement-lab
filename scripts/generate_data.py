"""Generate synthetic marketing data with known, planted problems.

Everything is fake and seeded, so every run produces the same CSVs.
Planted on purpose, so the checks in the dbt project have something to find:
  - duplicate purchase events (a tag firing twice)
  - click injection on one affiliate (click logged seconds before the order)

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
    write(tables)
