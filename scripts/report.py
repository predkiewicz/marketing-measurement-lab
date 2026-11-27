"""Print the results of a build and draw the geo test chart.

Usage: python scripts/report.py   (after dbt build)
Reads target/lab.duckdb, prints every result table, writes docs/geo_test.svg.
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
QUERIES = {
    "ROAS per channel, last click vs position-based": """
        select channel, revenue_last_click, revenue_position_based, roas_last_click, roas_position_based
        from fct_channel_roas order by revenue_position_based desc""",
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
    rows = con.sql("select geo_date, period, treatment_index, control_index from fct_geo_daily order by geo_date").fetchall()
    assert rows and any(r[1] == "test" for r in rows), "fct_geo_daily is empty or has no test period"
    out = ROOT / "docs" / "geo_test.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text(geo_chart(rows))
    print(f"\nWrote {out.relative_to(ROOT)}")
