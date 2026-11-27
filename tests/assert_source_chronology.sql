-- Intake checks that span columns or tables: what a single-column test cannot see.
-- Every row returned is a broken record. Bounds come from vars, not from the data under test.
select 'first order outside the observed window' as problem, order_id as record
from {{ ref('raw_orders') }}
where order_ts < cast('{{ var("data_start") }}' as timestamp)
    -- a first order needs its full value horizon observed, or its customer value is cut short
    or order_ts > cast('{{ var("observed_until") }}' as timestamp) - interval {{ var("value_horizon_days") }} day

union all
select 'repeat order before its first order, after the data ends, or for another user', r.repeat_order_id
from {{ ref('raw_repeat_orders') }} as r
inner join {{ ref('raw_orders') }} as o on o.order_id = r.first_order_id
where r.order_ts <= o.order_ts
    or r.order_ts > cast('{{ var("observed_until") }}' as timestamp)
    or r.user_id != o.user_id

union all
select 'touchpoint outside the data window', touchpoint_id
from {{ ref('raw_touchpoints') }}
where touch_ts < cast('{{ var("data_start") }}' as timestamp) - interval {{ var("lookback_days") }} day
    or touch_ts > cast('{{ var("observed_until") }}' as timestamp)

union all
select 'channel conversions above total conversions', test_channel || ' ' || holdout_date || ' ' || region_code
from {{ ref('raw_holdout_daily') }}
where conversions_channel > conversions_total

union all
select 'more consents than banner views', landing_channel || ' ' || device
from {{ ref('raw_consent_banner') }}
where accepted > banner_views
