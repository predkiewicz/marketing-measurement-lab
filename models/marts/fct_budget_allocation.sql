-- Where the budget freed by STOP decisions goes: to SCALE channels, so that the next euro earns the
-- same everywhere (equal marginal ROI). That is the split that buys the most 180-day gross profit.
--
-- On the response curve a channel at spend multiplier m earns marginal ROI = elasticity x ROI x
-- m ^ (elasticity - 1). For a common target marginal ROI (target_mroi), each channel's multiplier is therefore
-- (elasticity x ROI / target_mroi) ^ (1 / (1 - elasticity)), kept between 1 (SCALE channels are not cut)
-- and its profitable spend (where the next euro returns 1, capped at the tested range).
-- Lower target_mroi = more spend. The model searches a fine grid for the lowest target_mroi >= 1 whose spend
-- fits the freed budget. If even target_mroi = 1 fits, every channel sits at its profitable spend and the
-- rest of the money is not spent, because no measured channel would turn it into profit.
{% set steps = 4000 %}
with scale as (
    select
        channel,
        cost_eur,
        customers_incremental,
        gross_profit_per_customer_180d,
        elasticity,
        roi_180,
        profitable_spend_multiplier
    from {{ ref('fct_channel_decisions') }}
    where decision = 'SCALE'
),

freed as (
    select coalesce(sum(cost_eur), 0) as eur
    from {{ ref('fct_channel_decisions') }}
    where decision = 'STOP' and channel != 'regional_campaign'  -- the campaign is a separate budget
),

grid as (
    -- target_mroi from 1 (spend up to every profitable cap) to the highest marginal ROI today (spend nothing)
    select 1 + (n.generated_number - 1) * (max(s.elasticity * s.roi_180) - 1) / {{ steps }} as target_mroi
    from ({{ dbt.generate_series(steps + 1) }}) as n
    cross join scale as s
    group by n.generated_number
),

candidates as (
    select
        g.target_mroi,
        s.channel,
        least(greatest(power(s.elasticity * s.roi_180 / g.target_mroi, 1 / (1 - s.elasticity)), 1),
              s.profitable_spend_multiplier) as multiplier
    from grid as g
    cross join scale as s
),

best as (
    -- lowest target_mroi whose extra spend fits the freed budget
    select min(c.target_mroi) as target_mroi
    from (
        select target_mroi, sum(s.cost_eur * (c.multiplier - 1)) as extra_eur
        from candidates as c
        inner join scale as s on s.channel = c.channel
        group by target_mroi
    ) as c
    cross join freed as f
    where c.extra_eur <= f.eur
)

select
    s.channel,
    s.cost_eur,
    round(c.multiplier, 4) as spend_multiplier,
    round(s.cost_eur * (c.multiplier - 1), 2) as allocated_eur,
    -- the next euro after the allocation: equal across channels unless a channel sits at a bound
    round(s.elasticity * s.roi_180 * power(c.multiplier, s.elasticity - 1), 3) as marginal_roi_after,
    s.customers_incremental * (power(c.multiplier, s.elasticity) - 1) as customers_gained,
    s.customers_incremental * (power(c.multiplier, s.elasticity) - 1) * s.gross_profit_per_customer_180d as profit_gained,
    s.profitable_spend_multiplier
from scale as s
inner join candidates as c on c.channel = s.channel
inner join best as b on c.target_mroi = b.target_mroi
