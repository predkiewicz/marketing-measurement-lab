-- Placebo tests in space: every possible set of 6 of the 16 regions (8,008 sets) runs the geo
-- estimator on the days before the campaign, where the true effect is zero: the first 28 days as
-- baseline, the next 28 as a fake campaign. The spread of these estimates is the noise a real
-- readout has to beat, including regional drift that carries over from day to day. A standard error
-- that treats days as independent misses that drift and comes out too small.
with regions as (
    select region_code, row_number() over (order by region_code) as n
    from {{ ref('raw_geo_regions') }}
),

sets as (
    select
        r1.region_code || r2.region_code || r3.region_code || r4.region_code || r5.region_code || r6.region_code as set_id,
        r1.region_code as c1, r2.region_code as c2, r3.region_code as c3,
        r4.region_code as c4, r5.region_code as c5, r6.region_code as c6
    from regions as r1
    inner join regions as r2 on r2.n > r1.n
    inner join regions as r3 on r3.n > r2.n
    inner join regions as r4 on r4.n > r3.n
    inner join regions as r5 on r5.n > r4.n
    inner join regions as r6 on r6.n > r5.n
),

members as (
    select set_id, c1 as region_code from sets union all select set_id, c2 from sets
    union all select set_id, c3 from sets union all select set_id, c4 from sets
    union all select set_id, c5 from sets union all select set_id, c6 from sets
),

pre as (
    select
        geo_date,
        region_code,
        conversions,
        row_number() over (partition by region_code order by geo_date) as day
    from {{ ref('raw_geo_daily') }}
    where geo_date < cast('{{ var("geo_test_start") }}' as date)
),

totals as (
    select day, sum(conversions) as all_conversions from pre group by day
),

daily as (
    select
        m.set_id,
        p.day,
        sum(p.conversions) as treated,
        max(t.all_conversions) - sum(p.conversions) as control
    from members as m
    inner join pre as p on p.region_code = m.region_code
    inner join totals as t on t.day = p.day
    where p.day <= 56
    group by m.set_id, p.day
),

gaps as (
    select
        set_id,
        day,
        ln(treated / avg(case when day <= 28 then treated end) over (partition by set_id))
          - ln(control / avg(case when day <= 28 then control end) over (partition by set_id)) as log_gap
    from daily
)

select
    set_id,
    avg(case when day > 28 then log_gap end) - avg(case when day <= 28 then log_gap end) as lift_log,
    -- what the independent-days standard error would claim for this placebo
    sqrt(var_samp(case when day > 28 then log_gap end) / 28 + var_samp(case when day <= 28 then log_gap end) / 28) as naive_se
from gaps
group by set_id
