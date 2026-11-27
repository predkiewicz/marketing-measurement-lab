-- Cash view per decided channel: net cash per EUR 1,000 spent, by day since acquisition. Day 0 pays
-- the full spend and collects the first orders' gross profit; repeat orders then pay it back. Only the
-- customers a channel ADDED count. The day the line crosses zero is the payback day; a line that is
-- still below zero at the horizon never pays back, and the money stays under water.
{% set days = range(0, var("value_horizon_days") + 1, 30) %}
with value as (
    select channel, {% for day in days %}gross_profit_d{{ day }}{% if not loop.last %}, {% endif %}{% endfor %}
    from {{ ref('fct_channel_value') }}
    union all
    -- the regional campaign's customers are valued at the all-customer average, as in fct_channel_decisions
    select 'regional_campaign', {% for day in days %}avg(gross_profit_d{{ day }}){% if not loop.last %}, {% endif %}{% endfor %}
    from {{ ref('fct_customer_value') }}
),

d as (
    select
        d.channel,
        d.customers_incremental / d.cost_eur as customers_per_eur,
        {% for day in days %}v.gross_profit_d{{ day }}{% if not loop.last %}, {% endif %}{% endfor %}
    from {{ ref('fct_channel_decisions') }} as d
    inner join value as v on v.channel = d.channel
)

{% for day in days %}
select channel, {{ day }} as day, round(1000 * customers_per_eur * gross_profit_d{{ day }} - 1000, 0) as net_cash_per_1000_eur
from d
{% if not loop.last %}union all{% endif %}
{% endfor %}
