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
from {{ ref('int_order_paths') }}
