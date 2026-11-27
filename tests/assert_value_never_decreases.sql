-- Cumulative gross profit can only grow with time. Returns customers where it shrinks.
{% set days = range(0, var("value_horizon_days") + 1, 30) | list %}
select order_id
from {{ ref('fct_customer_value') }}
where {% for d in days[1:] %}gross_profit_d{{ d }} < gross_profit_d{{ days[loop.index0] }}{% if not loop.last %} or {% endif %}{% endfor %}
