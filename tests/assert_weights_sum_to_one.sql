-- Every order hands out exactly 100% credit under each model. Returns failing orders.
select order_id,
    sum(last_click_weight) as last_click_total,
    sum(position_based_weight) as position_based_total
from {{ ref('fct_attribution') }}
group by order_id
having abs(sum(last_click_weight) - 1) > 0.0001
    or abs(sum(position_based_weight) - 1) > 0.0001
