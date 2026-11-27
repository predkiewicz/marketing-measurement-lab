{#- Shared by the full-tracking and the consent-only views, so both use exactly the same logic. -#}

{% macro order_paths(touchpoints) %}
-- Every order with the touchpoints inside the lookback window before it, numbered in order.
-- Orders with no eligible touchpoint keep one row with channel 'unattributed', so revenue
-- never disappears. Touchpoints flagged as click injection earn no credit.
with paths as (
    select
        o.order_id,
        o.revenue_eur,
        t.touchpoint_id,
        coalesce(t.channel, 'unattributed') as channel,
        t.touch_ts
    from {{ ref('stg_orders') }} as o
    left join {{ touchpoints }} as t
        on t.user_id = o.user_id
        and t.touch_ts <= o.order_ts
        and {{ dbt.datediff('t.touch_ts', 'o.order_ts', 'day') }} <= {{ var('lookback_days') }}
        and t.touchpoint_id not in (select touchpoint_id from {{ ref('qa_click_injection') }})
)

select
    *,
    row_number() over (partition by order_id order by touch_ts, touchpoint_id) as touch_position,
    count(*) over (partition by order_id) as path_length
from paths
{% endmacro %}

{% macro attribution_weights(paths) %}
-- Credit per touchpoint under two models, side by side.
--   last_click:     100% to the last touch.
--   position_based: 40% first, 40% last, 20% shared by the middle touches.
--                   One touch gets 100%, two touches get 50/50.
select
    order_id,
    touchpoint_id,
    channel,
    touch_position,
    path_length,
    revenue_eur,
    case when touch_position = path_length then 1.0 else 0.0 end as last_click_weight,
    case
        when path_length = 1 then 1.0
        when path_length = 2 then 0.5
        when touch_position in (1, path_length) then 0.4
        else 0.2 / (path_length - 2)
    end as position_based_weight
from {{ paths }}
{% endmacro %}

{% macro decision(marginal_roi, roi, roi_worst, roi_best) %}
    case
        when {{ marginal_roi }} >= 1 and {{ roi_worst }} >= 1 then 'SCALE'
        when {{ roi_best }} < {{ var("stop_max_roi") }} then 'STOP'
        else 'TEST'
    end
{% endmacro %}
