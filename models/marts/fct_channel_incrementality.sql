-- Does a channel create conversions, or claim ones that would have arrived anyway?
-- For each holdout test: the drop in TOTAL conversions when the channel was off (difference-in-
-- differences, same estimator as fct_geo_test) divided by the conversions the channel would have
-- claimed. incrementality = 1: every claimed conversion is new. incrementality = 0: all of them
-- would have come anyway, as organic or unattributed.
with by_period as (
    select
        test_channel,
        period,
        avg(log_gap) as mean_gap,
        var_samp(log_gap) as var_gap,
        count(*) as days,
        sum(holdout_total) as holdout_total,
        sum(holdout_channel) as holdout_channel,
        sum(control_channel) as control_channel
    from {{ ref('fct_holdout_daily') }}
    group by test_channel, period
),

did as (
    select
        t.test_channel,
        t.mean_gap - p.mean_gap as effect_log,
        sqrt(t.var_gap / t.days + p.var_gap / p.days) as effect_log_se,
        t.holdout_total,
        -- what the channel would have claimed in the holdout regions: control's channel volume,
        -- scaled by the pre-test ratio between the groups, minus what it still claimed (zero)
        t.control_channel * p.holdout_channel / p.control_channel - t.holdout_channel as channel_conversions_lost
    from by_period as t
    inner join by_period as p on p.test_channel = t.test_channel
    where t.period = 'test' and p.period = 'pre'
),

effects as (
    select
        *,
        exp(effect_log) - 1 as effect,
        exp(effect_log - {{ var("geo_ci_z") }} * effect_log_se) - 1 as effect_low,
        exp(effect_log + {{ var("geo_ci_z") }} * effect_log_se) - 1 as effect_high
    from did
),

incremental as (
    -- conversions the holdout regions lost = counterfactual minus actual; a drop is a negative effect
    select
        *,
        holdout_total * -effect / (1 + effect) as incremental_conversions,
        holdout_total * -effect_high / (1 + effect_high) as incremental_low,
        holdout_total * -effect_low / (1 + effect_low) as incremental_high
    from effects
)

select
    test_channel as channel,
    round(effect, 4) as total_effect,
    round(effect_low, 4) as total_effect_low,
    round(effect_high, 4) as total_effect_high,
    round(channel_conversions_lost, 0) as channel_conversions_lost,
    round(incremental_conversions, 0) as incremental_conversions,
    round(incremental_conversions / channel_conversions_lost, 3) as incrementality,
    round(incremental_low / channel_conversions_lost, 3) as incrementality_low,
    round(incremental_high / channel_conversions_lost, 3) as incrementality_high,
    round(1 - incremental_conversions / channel_conversions_lost, 3) as share_taken_from_existing_demand,
    case
        when incremental_high / channel_conversions_lost < {{ var("incrementality_threshold") }}
            then 'mostly claims existing demand'
        when incremental_low / channel_conversions_lost > {{ var("incrementality_threshold") }}
            then 'mostly incremental'
        else 'inconclusive'
    end as verdict
from incremental
