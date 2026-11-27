-- Affiliate clicks logged only seconds before an order. A real user does not click
-- an ad and finish checkout in under {{ var('injection_threshold_s') }} seconds; this pattern
-- usually means the click was injected to claim the commission.
select
    t.touchpoint_id,
    t.user_id,
    t.channel,
    o.order_id,
    o.revenue_eur,
    {{ dbt.datediff('t.touch_ts', 'o.order_ts', 'second') }} as seconds_to_order
from {{ ref('stg_touchpoints') }} as t
join {{ ref('stg_orders') }} as o
    on o.user_id = t.user_id
    and t.touch_ts <= o.order_ts
where t.channel = 'affiliate'
    and {{ dbt.datediff('t.touch_ts', 'o.order_ts', 'second') }} < {{ var('injection_threshold_s') }}
