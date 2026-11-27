-- Every touchpoint inside the lookback window before an order, numbered in order.
-- Touchpoints flagged as click injection are excluded, so they earn no credit.
with paths as (
    select
        o.order_id,
        o.revenue_eur,
        t.touchpoint_id,
        t.channel,
        t.touch_ts
    from {{ ref('stg_orders') }} as o
    join {{ ref('stg_touchpoints') }} as t
        on t.user_id = o.user_id
        and t.touch_ts <= o.order_ts
        and {{ dbt.datediff('t.touch_ts', 'o.order_ts', 'day') }} <= {{ var('lookback_days') }}
    where t.touchpoint_id not in (select touchpoint_id from {{ ref('qa_click_injection') }})
)

select
    *,
    row_number() over (partition by order_id order by touch_ts, touchpoint_id) as touch_position,
    count(*) over (partition by order_id) as path_length
from paths
