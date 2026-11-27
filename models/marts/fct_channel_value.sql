-- Average gross profit per customer by channel and day, weighted by position-based credit: a
-- customer whose journey was 40% social counts 40% towards social's average.
{% set days = range(0, var("value_horizon_days") + 1, 30) %}
select
    a.channel,
    sum(a.position_based_weight) as customers,
    {% for d in days %}
    round(sum(a.position_based_weight * v.gross_profit_d{{ d }}) / sum(a.position_based_weight), 2) as gross_profit_d{{ d }}{% if not loop.last %},{% endif %}
    {% endfor %}
from {{ ref('fct_attribution') }} as a
inner join {{ ref('fct_customer_value') }} as v on v.order_id = a.order_id
group by a.channel
