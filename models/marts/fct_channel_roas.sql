-- Attributed revenue, cost and ROAS per channel under both models.
-- Affiliate cost is a fee per attributed order, so it moves with the model.
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
)

select
    c.channel,
    round(c.revenue_last_click, 2) as revenue_last_click,
    round(c.revenue_position_based, 2) as revenue_position_based,
    round(case when c.channel = 'affiliate' then c.revenue_last_click * {{ var("affiliate_fee") }}
               else coalesce(s.spend_eur, 0) end, 2) as cost_last_click,
    round(case when c.channel = 'affiliate' then c.revenue_position_based * {{ var("affiliate_fee") }}
               else coalesce(s.spend_eur, 0) end, 2) as cost_position_based,
    round(c.revenue_last_click / nullif(case when c.channel = 'affiliate'
        then c.revenue_last_click * {{ var("affiliate_fee") }} else s.spend_eur end, 0), 2) as roas_last_click,
    round(c.revenue_position_based / nullif(case when c.channel = 'affiliate'
        then c.revenue_position_based * {{ var("affiliate_fee") }} else s.spend_eur end, 0), 2) as roas_position_based
from credit as c
left join spend as s on s.channel = c.channel
