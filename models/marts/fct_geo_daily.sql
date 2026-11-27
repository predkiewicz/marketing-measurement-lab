-- Daily conversions per test group, as an index of the group's own pre-test average.
-- log_gap is the log ratio treatment / control: the series the geo test reads.
with daily as (
    select
        d.geo_date,
        r.test_group,
        sum(d.conversions) as conversions,
        sum(d.campaign_spend_eur) as campaign_spend_eur
    from {{ ref('raw_geo_daily') }} as d
    inner join {{ ref('raw_geo_regions') }} as r on r.region_code = d.region_code
    group by d.geo_date, r.test_group
),

baseline as (
    select test_group, avg(conversions) as baseline_per_day
    from daily
    where geo_date < cast('{{ var("geo_test_start") }}' as date)
    group by test_group
),

pivoted as (
    select
        d.geo_date,
        sum(case when d.test_group = 'treatment' then d.conversions end) as treatment_conversions,
        sum(case when d.test_group = 'control' then d.conversions end) as control_conversions,
        sum(case when d.test_group = 'treatment' then d.campaign_spend_eur end) as treatment_spend_eur,
        sum(case when d.test_group = 'treatment' then d.conversions / b.baseline_per_day end) as treatment_index,
        sum(case when d.test_group = 'control' then d.conversions / b.baseline_per_day end) as control_index
    from daily as d
    inner join baseline as b on b.test_group = d.test_group
    group by d.geo_date
)

select
    geo_date,
    case when geo_date < cast('{{ var("geo_test_start") }}' as date) then 'pre' else 'test' end as period,
    treatment_conversions,
    control_conversions,
    treatment_spend_eur,
    treatment_index,
    control_index,
    ln(treatment_index) - ln(control_index) as log_gap
from pivoted
