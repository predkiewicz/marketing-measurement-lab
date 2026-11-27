"""Size a geo test before it runs: simulation-based power on pre-campaign data.

Takes only the days before the campaign. First, every possible set of treatment regions runs the
same estimator as models/marts/fct_geo_test.sql with no effect added: the spread of those placebo
estimates sets the bar a real effect has to clear (as fct_geo_placebo does). Then random sets get a
known lift in a fake test window; power is the share that clears the bar. It also reports how
often an interval that treats days as independent raises a false alarm.

Usage: python scripts/geo_power.py [--sims N] [--seed S]
Reads seeds/raw_geo_daily.csv (run generate_data.py first). Prints a table, writes nothing.
"""
import argparse
import csv
import math
import random
from collections import defaultdict
from itertools import combinations
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


def null_estimates(regions, conv, test_days: int) -> list[tuple[float, float]]:
    """Placebo tests in space: every set of treated regions, no effect added. Returns (lift_log, naive se)."""
    window = BASELINE_DAYS + test_days
    out = []
    for treated in combinations(regions, GEO_TREATED):
        treat = [sum(conv[r][d] for r in treated) for d in range(window)]
        ctrl = [sum(conv[r][d] for r in regions if r not in treated) for d in range(window)]
        out.append(readout(treat, ctrl, BASELINE_DAYS))
    return out


def calibrate(null: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Critical value from half of the placebo sets, false-alarm rates measured on the other half."""
    fit, check = null[::2], null[1::2]
    mean = sum(x for x, _ in fit) / len(fit)
    crit = Z * (sum((x - mean) ** 2 for x, _ in fit) / (len(fit) - 1)) ** 0.5
    placebo_alarms = sum(abs(x) > crit for x, _ in check) / len(check)
    naive_alarms = sum(abs(x) > Z * se for x, se in check) / len(check)
    return crit, placebo_alarms, naive_alarms


def power(regions, conv, test_days: int, lift: float, crit: float, sims: int, rng: random.Random) -> float:
    window = BASELINE_DAYS + test_days
    hits = 0
    for _ in range(sims):
        treated = set(rng.sample(regions, GEO_TREATED))
        treat = [sum(conv[r][d] for r in treated) for d in range(window)]
        ctrl = [sum(conv[r][d] for r in regions if r not in treated) for d in range(window)]
        treat = treat[:BASELINE_DAYS] + [x * (1 + lift) for x in treat[BASELINE_DAYS:]]
        lift_log, _ = readout(treat, ctrl, BASELINE_DAYS)
        hits += lift_log > crit
    return hits / sims


def run(sims: int, seed: int) -> tuple[dict, dict]:
    regions, conv = load_pre_period()
    rng = random.Random(seed)
    calibration = {t: calibrate(null_estimates(regions, conv, t)) for t in TEST_LENGTHS}
    result = {(t, lift): power(regions, conv, t, lift, calibration[t][0], sims, rng)
              for t in TEST_LENGTHS for lift in LIFTS if lift > 0}
    return result, calibration


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sims", type=int, default=500)
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()
    result, calibration = run(a.sims, a.seed)

    print(f"Power of a geo test on this data: {GEO_TREATED} of 16 regions treated, {BASELINE_DAYS} days of "
          f"history, significance from all placebo region sets, {a.sims} random region sets per cell.\n")
    print("False alarms when nothing happened (should be 5%), measured on placebo sets not used for calibration:\n")
    print("| Interval from | " + " | ".join(f"{t} days" for t in TEST_LENGTHS) + " |")
    print("|---|" + "---:|" * len(TEST_LENGTHS))
    print("| Independent days (naive) | " + " | ".join(f"{calibration[t][2]:.0%}" for t in TEST_LENGTHS) + " |")
    print("| Placebo sets | " + " | ".join(f"{calibration[t][1]:.0%}" for t in TEST_LENGTHS) + " |")
    print("\nPower with placebo-calibrated significance:\n")
    print("| True lift | " + " | ".join(f"{t} days" for t in TEST_LENGTHS) + " |")
    print("|---|" + "---:|" * len(TEST_LENGTHS))
    for lift in LIFTS[2::2]:
        print(f"| {lift:.0%} | " + " | ".join(f"{result[(t, lift)]:.0%}" for t in TEST_LENGTHS) + " |")
    print()
    for t in TEST_LENGTHS:
        mde = next((lift for lift in LIFTS if lift > 0 and result[(t, lift)] >= 0.8), None)
        print(f"Smallest lift detected 80% of the time, {t} days: " + (f"{mde:.0%}" if mde else f"above {LIFTS[-1]:.0%}"))

    # self-check: same seed, same answer; placebo-calibrated false alarms near 5% on held-out sets;
    # more lift never means much less power
    assert run(50, a.seed) == run(50, a.seed)
    for t in TEST_LENGTHS:
        assert calibration[t][1] <= 0.07, f"false alarm rate too high at {t} days"
        powers = [result[(t, lift)] for lift in LIFTS if lift > 0]
        assert all(b >= a - 0.05 for a, b in zip(powers, powers[1:])), f"power not increasing at {t} days"
