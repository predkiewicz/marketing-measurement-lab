-- Placebo test: split the pre-test period in two halves and run the same estimator. Nothing changed
-- between the halves, so the interval must contain zero. If it does not, treatment and control were
-- already drifting apart before the campaign and the readout cannot be trusted. Returns a row on failure.
with pre as (
    select
        log_gap,
        case when row_number() over (order by geo_date) <= count(*) over () / 2
             then 'first' else 'second' end as half
    from {{ ref('fct_geo_daily') }}
    where period = 'pre'
),

by_half as (
    select half, avg(log_gap) as mean_gap, var_samp(log_gap) as var_gap, count(*) as days
    from pre
    group by half
),

placebo as (
    select
        s.mean_gap - f.mean_gap as lift_log,
        sqrt(s.var_gap / s.days + f.var_gap / f.days) as lift_log_se
    from by_half as s
    cross join by_half as f
    where s.half = 'second' and f.half = 'first'
)

select *
from placebo
where abs(lift_log) > {{ var("geo_ci_z") }} * lift_log_se
