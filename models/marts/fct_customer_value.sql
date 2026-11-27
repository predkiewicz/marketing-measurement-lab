-- Gross profit per customer, cumulative by day since the first order (day 0 = the first order
-- itself), up to value_horizon_days. Gross profit = revenue x gross_margin.
{% set days = range(0, var("value_horizon_days") + 1, 30) %}
select
    o.order_id,
    o.user_id,
    {% for d in days %}
    round((o.revenue_eur + coalesce(sum(case when {{ dbt.datediff('o.order_ts', 'r.order_ts', 'day') }} <= {{ d }}
        then r.revenue_eur end), 0)) * {{ var("gross_margin") }}, 2) as gross_profit_d{{ d }}{% if not loop.last %},{% endif %}
    {% endfor %}
from {{ ref('stg_orders') }} as o
left join {{ ref('raw_repeat_orders') }} as r on r.first_order_id = o.order_id
group by o.order_id, o.user_id, o.revenue_eur
