"""Size a geo test before it runs: simulation-based power on pre-campaign data.

Takes only the days before the campaign, picks random sets of treatment regions, adds a known
lift to them in a fake test window, and runs the same estimator as models/marts/fct_geo_test.sql
(difference-in-differences on the daily log gap, 95% interval). Power is the share of simulated
tests whose interval lies above zero. The row with no lift shows how often the test raises a
false alarm.

Usage: python scripts/geo_power.py [--sims N] [--seed S]
Reads seeds/raw_geo_daily.csv (run generate_data.py first). Prints a table, writes nothing.
"""
import argparse
import csv
import math
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from generate_data import GEO_PRE_DAYS, GEO_START, GEO_TREATED

SEEDS = Path(__file__).resolve().parent.parent / "seeds"
Z = 1.96
BASELINE_DAYS = 28            # history the simulated test compares against
TEST_LENGTHS = (14, 28)       # days the simulated campaign runs
LIFTS = tuple(i / 100 for i in range(13))  # 0% to 12%; the table shows every second one


def load_pre_period() -> tuple[list[str], dict[str, list[int]]]:
    """Daily conversions per region for the days before the campaign, in date order."""
    end = GEO_START.date() + timedelta(days=GEO_PRE_DAYS)
    by_region = defaultdict(dict)
    with open(SEEDS / "raw_geo_daily.csv") as f:
        for row in csv.DictReader(f):
            day = date.fromisoformat(row["geo_date"])
            if day < end:
                by_region[row["region_code"]][day] = int(row["conversions"])
    days = sorted(next(iter(by_region.values())))
    return sorted(by_region), {r: [v[d] for d in days] for r, v in by_region.items()}


def readout(treat: list[float], ctrl: list[float], n_pre: int) -> tuple[float, float]:
    """Same estimator as fct_geo_test: log lift and its standard error from daily group totals."""
    def index(series):
        base = sum(series[:n_pre]) / n_pre
        return [x / base for x in series]
    gap = [math.log(t) - math.log(c) for t, c in zip(index(treat), index(ctrl))]
    pre, test = gap[:n_pre], gap[n_pre:]
    mean = lambda xs: sum(xs) / len(xs)
    var = lambda xs: sum((x - mean(xs)) ** 2 for x in xs) / (len(xs) - 1)
    return mean(test) - mean(pre), math.sqrt(var(test) / len(test) + var(pre) / len(pre))


def power(regions, conv, test_days: int, lift: float, sims: int, rng: random.Random) -> float:
    window = BASELINE_DAYS + test_days
    hits = 0
    for _ in range(sims):
        treated = set(rng.sample(regions, GEO_TREATED))
        treat = [sum(conv[r][d] for r in treated) for d in range(window)]
        ctrl = [sum(conv[r][d] for r in regions if r not in treated) for d in range(window)]
        treat = treat[:BASELINE_DAYS] + [x * (1 + lift) for x in treat[BASELINE_DAYS:]]
        lift_log, se = readout(treat, ctrl, BASELINE_DAYS)
        hits += lift_log - Z * se > 0
    return hits / sims


def run(sims: int, seed: int) -> dict[tuple[int, float], float]:
    regions, conv = load_pre_period()
    rng = random.Random(seed)
    return {(t, lift): power(regions, conv, t, lift, sims, rng) for t in TEST_LENGTHS for lift in LIFTS}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sims", type=int, default=500)
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()
    result = run(a.sims, a.seed)

    print(f"Power of a geo test on this data: {GEO_TREATED} of 16 regions treated, {BASELINE_DAYS} days of "
          f"history, 95% interval, {a.sims} random region sets per cell.\n")
    print("| True lift | " + " | ".join(f"{t} days" for t in TEST_LENGTHS) + " |")
    print("|---|" + "---:|" * len(TEST_LENGTHS))
    for lift in LIFTS[::2]:
        label = "0% (false alarms)" if lift == 0 else f"{lift:.0%}"
        print(f"| {label} | " + " | ".join(f"{result[(t, lift)]:.0%}" for t in TEST_LENGTHS) + " |")
    print()
    for t in TEST_LENGTHS:
        mde = next((lift for lift in LIFTS if lift > 0 and result[(t, lift)] >= 0.8), None)
        print(f"Smallest lift detected 80% of the time, {t} days: " + (f"{mde:.0%}" if mde else f"above {LIFTS[-1]:.0%}"))

    # self-check: same seed, same answer; false alarms near 5%; more lift never means much less power
    assert run(50, a.seed) == run(50, a.seed)
    for t in TEST_LENGTHS:
        assert result[(t, 0.0)] <= 0.10, f"false alarm rate too high at {t} days"
        powers = [result[(t, lift)] for lift in LIFTS]
        assert all(b >= a - 0.05 for a, b in zip(powers, powers[1:])), f"power not increasing at {t} days"
