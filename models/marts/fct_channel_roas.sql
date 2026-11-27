-- Attributed revenue, cost and ROAS per channel under both models.
-- Affiliate cost is the commission the network invoices: a fee on the orders it claims by last
-- click. It does not change with our attribution model, so affiliate ROAS is exactly 1 / fee under
-- last click and lower under position-based, where affiliates get less revenue for the same cost.
with credit as (
    select
        channel,
        sum(revenue_eur * last_click_weight) as revenue_last_click,
        sum(revenue_eur * position_based_weight) as revenue_position_based
    from {{ ref('fct_attribution') }}
    group by channel
),

spend as (
    select channel, sum(spend_eur) as spend_eur
    from {{ ref('raw_ad_spend') }}
    group by channel
),

costed as (
    select
        c.*,
        case when c.channel = 'affiliate' then c.revenue_last_click * {{ var("affiliate_fee") }}
             else coalesce(s.spend_eur, 0) end as cost_eur
    from credit as c
    left join spend as s on s.channel = c.channel
)

select
    channel,
    round(revenue_last_click, 2) as revenue_last_click,
    round(revenue_position_based, 2) as revenue_position_based,
    round(cost_eur, 2) as cost_eur,
    round(revenue_last_click / nullif(cost_eur, 0), 2) as roas_last_click,
    round(revenue_position_based / nullif(cost_eur, 0), 2) as roas_position_based
from costed
