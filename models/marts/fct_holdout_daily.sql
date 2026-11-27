-- Channel holdout tests, one row per test and day. In the holdout regions the tested channel was
-- switched off during the test period. Totals are indexed to each group's own pre-test average;
-- log_gap is the log ratio holdout / control, the same series the geo test reads.
with daily as (
    select
        test_channel,
        holdout_date,
        is_test_period,
        sum(case when is_holdout_region then conversions_total end) as holdout_total,
        sum(case when not is_holdout_region then conversions_total end) as control_total,
        sum(case when is_holdout_region then conversions_channel end) as holdout_channel,
        sum(case when not is_holdout_region then conversions_channel end) as control_channel
    from {{ ref('raw_holdout_daily') }}
    group by test_channel, holdout_date, is_test_period
),

baseline as (
    select
        test_channel,
        avg(holdout_total) as holdout_base,
        avg(control_total) as control_base
    from daily
    where not is_test_period
    group by test_channel
)

select
    d.test_channel,
    d.holdout_date,
    case when d.is_test_period then 'test' else 'pre' end as period,
    d.holdout_total,
    d.control_total,
    d.holdout_channel,
    d.control_channel,
    ln(d.holdout_total / b.holdout_base) - ln(d.control_total / b.control_base) as log_gap
from daily as d
inner join baseline as b on b.test_channel = d.test_channel
