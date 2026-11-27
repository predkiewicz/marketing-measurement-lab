-- Cost per acquired customer per channel, three ways. Every customer orders once in this data,
-- so customers = orders.
--   last click / position-based: cost divided by the customers each attribution model credits.
--   incremental: cost divided by the customers the channel actually added, i.e. position-based
--   customers times the incrementality measured in the channel's holdout test. Channels without a
--   holdout test (email, organic, unattributed) have no incremental figure.
with customers as (
    select
        channel,
        sum(last_click_weight) as customers_last_click,
        sum(position_based_weight) as customers_position_based
    from {{ ref('fct_attribution') }}
    group by channel
)

select
    c.channel,
    r.cost_eur,
    c.customers_last_click,
    c.customers_position_based,
    i.incrementality,
    c.customers_position_based * i.incrementality as customers_incremental,
    -- no cost, no CAC: email, organic and unattributed show NULL, not a misleading zero
    round(nullif(r.cost_eur, 0) / nullif(c.customers_last_click, 0), 2) as cac_last_click,
    round(nullif(r.cost_eur, 0) / nullif(c.customers_position_based, 0), 2) as cac_position_based,
    round(nullif(r.cost_eur, 0) / nullif(c.customers_position_based * i.incrementality, 0), 2) as cac_incremental
from customers as c
inner join {{ ref('fct_channel_roas') }} as r on r.channel = c.channel
left join {{ ref('fct_channel_incrementality') }} as i on i.channel = c.channel
