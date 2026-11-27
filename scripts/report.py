"""Print the results of a build and draw the geo test chart.

Usage: python scripts/report.py   (after dbt build)
Reads target/lab.duckdb, prints every result table, writes docs/decisions.svg, docs/response_curves.svg and docs/geo_test.svg.
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
QUERIES = {
    "Decisions per channel": """
        select channel, decision, cost_eur, cac_incremental, gross_profit_per_customer_180d as gp_180d,
               roi_180_worst, roi_180, roi_180_best, marginal_roi_180 as marginal_roi,
               profitable_spend_multiplier as profitable_spend, payback_days, flagged_fraud_clicks as fraud_clicks, reason
        from fct_channel_decisions order by roi_180 desc""",
    "Freed budget per SCALE channel (equal marginal ROI)": """
        select channel, cost_eur, spend_multiplier, allocated_eur, marginal_roi_after,
               round(customers_gained, 1) as customers_gained, profitable_spend_multiplier
        from fct_budget_allocation order by allocated_eur desc""",
    "Consent: what tracking sees and what modelling recovers": """
        select channel, consent_rate, customers_true, customers_observed, customers_modelled,
               observed_error, modelled_error, cac_true, cac_observed, cac_modelled,
               decision_true, decision_observed, decision_modelled
        from fct_consent_impact order by customers_true desc""",
    "Budget plan before and after the decisions": """
        select plan, cost_eur, customers, blended_cac, gross_profit_180d, profit_after_marketing_180d, roi_180, meets_cac_goal
        from fct_budget_scenario order by sort""",
    "Net cash per EUR 1,000 spent, by day since acquisition (incremental customers)": """
        pivot fct_channel_cashflow on day in (0, 30, 60, 90, 120, 150, 180) using sum(net_cash_per_1000_eur) group by channel order by channel""",
    "Gross profit per customer by day since first order": """
        select * exclude (customers) from fct_channel_value order by gross_profit_d180 desc""",
    "ROAS per channel, last click vs position-based": """
        select channel, revenue_last_click, revenue_position_based, roas_last_click, roas_position_based
        from fct_channel_roas order by revenue_position_based desc""",
    "CAC per channel: attributed vs incremental": """
        select channel, cost_eur, round(customers_last_click, 1) as customers_lc,
               round(customers_position_based, 1) as customers_pb, incrementality,
               round(customers_incremental, 1) as customers_incr,
               cac_last_click, cac_position_based, cac_incremental
        from fct_channel_cac order by cost_eur desc, channel""",
    "Blended CAC views": """
        select view, cost_eur, customers, cac from fct_blended_cac order by sort""",
    "Response curves (budget-step tests)": """
        select * from fct_response_curves order by elasticity desc""",
    "Incrementality per channel (holdout tests)": """
        select channel, channel_conversions_lost, incremental_conversions, incrementality,
               incrementality_low, incrementality_high, share_taken_from_existing_demand, verdict
        from fct_channel_incrementality order by incrementality desc""",
    "Tracking QA": """
        select 'duplicate purchase events' as check_name, count(*) as findings,
               round(sum(revenue_overstated_eur), 2) as revenue_eur from qa_duplicate_orders
        union all
        select 'affiliate click injection', count(*), round(sum(revenue_eur), 2) from qa_click_injection""",
    "Geo test readout": """
        select test_days, lift, lift_low, lift_high, is_significant, incremental_conversions,
               campaign_spend_eur, incremental_cpa_eur, incremental_cpa_best_eur, incremental_cpa_worst_eur
        from fct_geo_test""",
}


DECISION_COLORS = {"SCALE": "#0ca30c", "TEST": "#fab219", "STOP": "#d03b3b"}  # status: good / warning / critical


def decision_chart(rows: list[tuple]) -> str:
    """ROI on incremental customers per channel: worst to best range, expected value, decision label."""
    w, row_h, left, right, top = 760, 44, 150, 150, 64
    h = top + row_h * len(rows) + 40
    hi = max(2.0, max(r[3] for r in rows) * 1.05)
    x = lambda v: left + v * (w - left - right) / hi
    marks = []
    for i, (channel, decision, worst, best, roi) in enumerate(rows):
        y = top + row_h * i + row_h / 2
        color = DECISION_COLORS[decision]
        marks.append(
            f'<text class="label" x="{left - 12}" y="{y + 4:.1f}" text-anchor="end">{channel.replace("_", " ")}</text>'
            f'<line x1="{x(worst):.1f}" x2="{x(best):.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="6" stroke-linecap="round"/>'
            f'<circle class="dot" cx="{x(roi):.1f}" cy="{y:.1f}" r="7" fill="{color}"/>'
            f'<text class="label" x="{w - right + 16}" y="{y + 4:.1f}" font-weight="600">{decision}</text>'
            f'<text class="axis" x="{w - right + 70}" y="{y + 4:.1f}">{roi:.2f}</text>')
    refs = "".join(
        f'<line class="ref" x1="{x(v):.1f}" x2="{x(v):.1f}" y1="{top - 8}" y2="{h - 32}"/>'
        f'<text class="axis" x="{x(v) + dx:.1f}" y="{top - 14}" text-anchor="{anchor}">{label}</text>'
        for v, label, anchor, dx in ((1.0, "pays back: 1.0", "end", 4), (1.5, "1.5: scale", "start", -4)))
    ticks = "".join(f'<text class="axis" x="{x(v):.1f}" y="{h - 14}" text-anchor="middle">{v:.1f}</text>'
                    for v in [i / 2 for i in range(int(hi * 2) + 1)])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="system-ui, sans-serif" font-size="12" role="img" aria-label="Return on incremental customers after 180 days per channel, worst to best case, with the decision: {"; ".join(f"{r[0]} {r[1]} at {r[4]:.2f}" for r in rows)}.">
<style>
  .bg {{ fill: #fcfcfb }} .ref {{ stroke: #9e9d98; stroke-width: 1; stroke-dasharray: 4 4 }} .axis {{ fill: #52514e }}
  .title {{ fill: #0b0b0b; font-weight: 600; font-size: 14px }} .label {{ fill: #0b0b0b }} .dot {{ stroke: #fcfcfb; stroke-width: 2 }}
  @media (prefers-color-scheme: dark) {{
    .bg {{ fill: #1a1a19 }} .ref {{ stroke: #6b6a65 }} .axis {{ fill: #c3c2b7 }} .title, .label {{ fill: #f0efec }} .dot {{ stroke: #1a1a19 }}
  }}
</style>
<rect class="bg" width="{w}" height="{h}" rx="8"/>
<text class="title" x="16" y="24">180-day gross profit per euro spent, on customers the channel added (worst to best case)</text>
{refs}{"".join(marks)}{ticks}
</svg>
"""


CURVE_COLORS = [("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70")]  # light, dark


def curve_chart(rows: list[tuple]) -> str:
    """Marginal ROI of the next euro against spend (multiple of today), one line per channel."""
    w, h, left, right, top, bottom = 760, 340, 56, 190, 40, 44
    x_max, y_max = 3.0, 2.0
    x = lambda m: left + m * (w - left - right) / x_max
    y = lambda v: top + (y_max - min(v, y_max)) * (h - top - bottom) / y_max
    styles, lines = [], []
    for i, (channel, elasticity, roi, profitable) in enumerate(rows):
        light, dark = CURVE_COLORS[i]
        styles.append(f".c{i} {{ stroke: {light} }} .f{i} {{ fill: {light} }}")
        styles.append(f"@media (prefers-color-scheme: dark) {{ .c{i} {{ stroke: {dark} }} .f{i} {{ fill: {dark} }} }}")
        ms = [0.25 + k * (x_max - 0.25) / 110 for k in range(111)]
        pts = " ".join(f"{x(m):.1f},{y(elasticity * roi * m ** (elasticity - 1)):.1f}" for m in ms)
        lines.append(f'<polyline class="c{i}" points="{pts}"/>')
        today = elasticity * roi
        lines.append(f'<circle class="f{i} dot" cx="{x(1):.1f}" cy="{y(today):.1f}" r="5"/>')
        end = elasticity * roi * x_max ** (elasticity - 1)
        if 1 < profitable < x_max:  # where the next euro stops paying back
            lines.append(f'<circle class="c{i} ring" cx="{x(profitable):.1f}" cy="{y(1):.1f}" r="6"/>')
        lines.append(f'<text class="label" x="{x(x_max) + 8:.1f}" y="{y(end) + 4 + 12 * (i - 1):.1f}">{channel.replace("_", " ")}: '
                     f'{"profitable to " + format(profitable, ".2f") + "x" if profitable >= 1 else "past it today"}</text>')
    grid = "".join(f'<line class="grid" x1="{left}" x2="{x(x_max):.1f}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                   f'<text class="axis" x="{left - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v:.1f}</text>'
                   for v in (0, 0.5, 1.5, 2.0))
    xt = "".join(f'<text class="axis" x="{x(m):.1f}" y="{h - 22}" text-anchor="middle">{m:g}x</text>' for m in (0.5, 1, 1.5, 2, 2.5, 3))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="system-ui, sans-serif" font-size="12" role="img" aria-label="Marginal ROI of the next euro against spend as a multiple of today, per channel. {"; ".join(f"{r[0]}: marginal ROI {r[1] * r[2]:.2f} today" for r in rows)}.">
<style>
  .bg {{ fill: #fcfcfb }} .grid {{ stroke: #e4e3df }} .ref {{ stroke: #52514e; stroke-dasharray: 4 4 }} .axis {{ fill: #52514e }}
  .title {{ fill: #0b0b0b; font-weight: 600; font-size: 14px }} .label {{ fill: #0b0b0b }} .dot {{ stroke: #fcfcfb; stroke-width: 2 }}
  polyline {{ fill: none; stroke-width: 2 }} .ring {{ fill: none; stroke-width: 2 }}
  @media (prefers-color-scheme: dark) {{
    .bg {{ fill: #1a1a19 }} .grid {{ stroke: #383835 }} .ref {{ stroke: #c3c2b7 }} .axis {{ fill: #c3c2b7 }}
    .title, .label {{ fill: #f0efec }} .dot {{ stroke: #1a1a19 }}
  }}
  {" ".join(styles)}
</style>
<rect class="bg" width="{w}" height="{h}" rx="8"/>
<text class="title" x="16" y="24">180-day gross profit from the next euro, by spend level (dot = today)</text>
{grid}
<line class="ref" x1="{left}" x2="{x(x_max):.1f}" y1="{y(1):.1f}" y2="{y(1):.1f}"/>
<text class="axis" x="{left - 8}" y="{y(1) + 4:.1f}" text-anchor="end">1.0</text>
<text class="axis" x="{x(x_max) - 4:.1f}" y="{y(1) - 6:.1f}" text-anchor="end">below this line, the next euro loses money</text>
<line class="ref" x1="{x(1):.1f}" x2="{x(1):.1f}" y1="{top}" y2="{h - bottom}" stroke-opacity="0.4"/>
{"".join(lines)}
{xt}
<text class="axis" x="{x(1.5):.1f}" y="{h - 6}" text-anchor="middle">spend as a multiple of today</text>
</svg>
"""


def geo_chart(rows: list[tuple]) -> str:
    """Treatment and control index, 7-day trailing average, test window shaded. Static SVG with a dark mode."""
    # ponytail: trailing 7-day mean removes the shared weekend dip; the first 6 days are dropped
    rows = [(rows[i][0], rows[i][1], sum(r[2] for r in rows[i - 6:i + 1]) / 7, sum(r[3] for r in rows[i - 6:i + 1]) / 7)
            for i in range(6, len(rows))]
    w, h, left, right, top, bottom = 760, 320, 48, 96, 36, 36
    lo = min(min(t, c) for _, _, t, c in rows) - 0.02
    hi = max(max(t, c) for _, _, t, c in rows) + 0.02
    x = lambda i: left + i * (w - left - right) / (len(rows) - 1)
    y = lambda v: top + (hi - v) * (h - top - bottom) / (hi - lo)
    start = next(i for i, r in enumerate(rows) if r[1] == "test")

    def line(col: int) -> str:
        return " ".join(f"{x(i):.1f},{y(r[col]):.1f}" for i, r in enumerate(rows))

    ticks = [v / 100 for v in range(int(lo * 100) // 5 * 5 + 5, int(hi * 100) + 1, 5)]
    grid = "".join(
        f'<line class="grid" x1="{left}" x2="{w - right}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
        f'<text class="axis" x="{left - 6}" y="{y(v) + 4:.1f}" text-anchor="end" >{v:.2f}</text>' for v in ticks)
    last = len(rows) - 1
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="system-ui, sans-serif" font-size="12" role="img" aria-label="Geo test: 7-day average conversions of treatment and control regions, each indexed to its own pre-test average. The two lines move together before the campaign; treatment sits above control during the 28-day test.">
<style>
  .bg {{ fill: #fcfcfb }} .grid {{ stroke: #e4e3df; stroke-width: 1 }} .axis {{ fill: #52514e }}
  .title {{ fill: #0b0b0b; font-weight: 600; font-size: 14px }} .label {{ fill: #0b0b0b }}
  .window {{ fill: #f0efec }} .treat {{ stroke: #2a78d6 }} .ctrl {{ stroke: #eb6834 }}
  .dot-t {{ fill: #2a78d6 }} .dot-c {{ fill: #eb6834 }}
  @media (prefers-color-scheme: dark) {{
    .bg {{ fill: #1a1a19 }} .grid {{ stroke: #383835 }} .axis {{ fill: #c3c2b7 }}
    .title, .label {{ fill: #f0efec }} .window {{ fill: #262624 }}
    .treat {{ stroke: #3987e5 }} .ctrl {{ stroke: #d95926 }} .dot-t {{ fill: #3987e5 }} .dot-c {{ fill: #d95926 }}
  }}
  polyline {{ fill: none; stroke-width: 2; stroke-linejoin: round }}
</style>
<rect class="bg" width="{w}" height="{h}" rx="8"/>
<text class="title" x="{left}" y="22">Conversions, 7-day average, indexed to each group's pre-test average (1.0)</text>
<rect class="window" x="{x(start):.1f}" y="{top}" width="{x(last) - x(start):.1f}" height="{h - top - bottom}"/>
<text class="axis" x="{x(start) + 6:.1f}" y="{top + 14}">Campaign live in treatment regions</text>
{grid}
<polyline class="ctrl" points="{line(3)}"/>
<polyline class="treat" points="{line(2)}"/>
<circle class="dot-c" cx="{x(last):.1f}" cy="{y(rows[last][3]):.1f}" r="4"/>
<circle class="dot-t" cx="{x(last):.1f}" cy="{y(rows[last][2]):.1f}" r="4"/>
<text class="label" x="{x(last) + 8:.1f}" y="{min(y(rows[last][2]), y(rows[last][3]) - 14) + 4:.1f}">Treatment</text>
<text class="label" x="{x(last) + 8:.1f}" y="{max(y(rows[last][3]), y(rows[last][2]) + 14) + 4:.1f}">Control</text>
<text class="axis" x="{left}" y="{h - 12}">{rows[0][0]}</text>
<text class="axis" x="{x(start):.1f}" y="{h - 12}" text-anchor="middle">{rows[start][0]}</text>
<text class="axis" x="{x(last):.1f}" y="{h - 12}" text-anchor="end">{rows[last][0]}</text>
</svg>
"""


if __name__ == "__main__":
    con = duckdb.connect(str(ROOT / "target" / "lab.duckdb"), read_only=True)
    for title, sql in QUERIES.items():
        print(f"\n{title}")
        con.sql(sql).show(max_width=200)
    decisions = con.sql("""select channel, decision, roi_180_worst, roi_180_best, roi_180
                            from fct_channel_decisions order by roi_180 desc""").fetchall()
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "decisions.svg").write_text(decision_chart(decisions))
    print("\nWrote docs/decisions.svg")
    curves = con.sql("""select channel, elasticity, roi_180, profitable_spend_multiplier
                         from fct_channel_decisions where elasticity is not null order by roi_180 desc""").fetchall()
    (ROOT / "docs" / "response_curves.svg").write_text(curve_chart(curves))
    print("Wrote docs/response_curves.svg")
    rows = con.sql("select geo_date, period, treatment_index, control_index from fct_geo_daily order by geo_date").fetchall()
    assert rows and any(r[1] == "test" for r in rows), "fct_geo_daily is empty or has no test period"
    out = ROOT / "docs" / "geo_test.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text(geo_chart(rows))
    print(f"\nWrote {out.relative_to(ROOT)}")
