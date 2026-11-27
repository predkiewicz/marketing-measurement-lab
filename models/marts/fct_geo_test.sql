-- Geo test readout: difference-in-differences on the daily log gap, with a confidence interval.
-- Lift is relative: how much more the treatment regions converted than they would have without
-- the campaign. Same estimator as scripts/geo_power.py, which sizes the test before it runs.
--
-- The interval comes from the placebo distribution (fct_geo_placebo): the spread of the same
-- estimator on 8,008 region sets where nothing happened. A standard error that treats days as
-- independent (kept as lift_low_naive / lift_high_naive) is too narrow when regional series drift.
with by_period as (
    select
        period,
        avg(log_gap) as mean_gap,
        var_samp(log_gap) as var_gap,
        count(*) as days,
        sum(treatment_conversions) as treatment_conversions,
        sum(treatment_spend_eur) as treatment_spend_eur
    from {{ ref('fct_geo_daily') }}
    group by period
),

did as (
    select
        t.mean_gap - p.mean_gap as lift_log,
        sqrt(t.var_gap / t.days + p.var_gap / p.days) as lift_log_se,
        t.days as test_days,
        t.treatment_conversions,
        t.treatment_spend_eur
    from by_period as t
    cross join by_period as p
    where t.period = 'test' and p.period = 'pre'
),

placebo as (
    select stddev_samp(lift_log) as placebo_se from {{ ref('fct_geo_placebo') }}
),

lifts as (
    select
        *,
        exp(lift_log) - 1 as lift,
        exp(lift_log - {{ var("geo_ci_z") }} * pl.placebo_se) - 1 as lift_low,
        exp(lift_log + {{ var("geo_ci_z") }} * pl.placebo_se) - 1 as lift_high,
        exp(lift_log - {{ var("geo_ci_z") }} * lift_log_se) - 1 as lift_low_naive,
        exp(lift_log + {{ var("geo_ci_z") }} * lift_log_se) - 1 as lift_high_naive,
        pl.placebo_se,
        -- share of placebo sets with an effect at least this large, in either direction
        (select avg(case when abs(x.lift_log) >= abs(did.lift_log) then 1.0 else 0 end)
         from {{ ref('fct_geo_placebo') }} as x) as p_value
    from did
    cross join placebo as pl
),

incremental as (
    -- actual conversions minus what the treatment regions would have done without the campaign
    select
        *,
        treatment_conversions * lift / (1 + lift) as incremental_conversions,
        treatment_conversions * lift_low / (1 + lift_low) as incremental_low,
        treatment_conversions * lift_high / (1 + lift_high) as incremental_high
    from lifts
)

select
    test_days,
    round(lift, 4) as lift,
    round(lift_low, 4) as lift_low,
    round(lift_high, 4) as lift_high,
    lift_low > 0 as is_significant,
    round(p_value, 4) as p_value,
    round(lift_low_naive, 4) as lift_low_naive,
    round(lift_high_naive, 4) as lift_high_naive,
    round(lift_log_se, 4) as naive_se,
    round(placebo_se, 4) as placebo_se,
    round(incremental_conversions, 0) as incremental_conversions,
    round(incremental_low, 0) as incremental_conversions_low,
    round(incremental_high, 0) as incremental_conversions_high,
    round(treatment_spend_eur, 2) as campaign_spend_eur,
    round(treatment_spend_eur / nullif(incremental_conversions, 0), 2) as incremental_cpa_eur,
    round(treatment_spend_eur / nullif(incremental_high, 0), 2) as incremental_cpa_best_eur,
    round(case when incremental_low > 0 then treatment_spend_eur / incremental_low end, 2) as incremental_cpa_worst_eur
from incremental
