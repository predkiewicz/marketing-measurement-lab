-- What the decisions do to the always-on budget (attribution period).
--   STOP channels lose their cost and only their ADDED customers.
--   SCALE channels take the freed budget, but only up to their profitable spend (where the next euro
--   stops paying back, from the response curve). Budget beyond that is not spent: spending it would
--   lower profit. Added customers follow the curve: today x multiplier ^ elasticity.
--   TEST channels stay as they are. The regional campaign is a separate budget, not part of this plan.
with d as (
    select * from {{ ref('fct_channel_decisions') }} where channel != 'regional_campaign'
),

current_plan as (
    select
        (select sum(cost_eur) from {{ ref('fct_channel_cac') }}) as cost_eur,
        (select count(*) from {{ ref('stg_orders') }}) as customers,
        (select sum(gross_profit_d{{ var("value_horizon_days") }}) from {{ ref('fct_customer_value') }}) as gross_profit_180d
),

moves as (
    select
        sum(case when decision = 'STOP' then cost_eur else 0 end) as freed_eur,
        sum(case when decision = 'STOP' then customers_incremental else 0 end) as customers_lost,
        sum(case when decision = 'STOP' then customers_incremental * gross_profit_per_customer_180d else 0 end) as profit_lost,
        sum(case when decision = 'SCALE' then cost_eur else 0 end) as scale_cost
    from d
),

allocation as (
    -- ponytail: freed budget split in proportion to today's cost, each channel capped at its profitable
    -- spend; with several SCALE channels, equalising marginal ROI would allocate better
    select
        d.*,
        least(m.freed_eur * d.cost_eur / m.scale_cost, d.cost_eur * (d.profitable_spend_multiplier - 1)) as allocated_eur
    from d
    cross join moves as m
    where d.decision = 'SCALE'
),

gains as (
    select
        sum(allocated_eur) as allocated_eur,
        sum(customers_incremental * (power(1 + allocated_eur / cost_eur, elasticity) - 1)) as customers_gained,
        sum(customers_incremental * (power(1 + allocated_eur / cost_eur, elasticity) - 1)
            * gross_profit_per_customer_180d) as profit_gained
    from allocation
),

plans as (
    select 1 as sort, 'Current plan' as plan, cost_eur, customers, gross_profit_180d from current_plan
    union all
    select 2, 'After decisions',
        c.cost_eur - m.freed_eur + coalesce(g.allocated_eur, 0),
        c.customers - m.customers_lost + coalesce(g.customers_gained, 0),
        c.gross_profit_180d - m.profit_lost + coalesce(g.profit_gained, 0)
    from current_plan as c
    cross join moves as m
    cross join gains as g
)

select
    sort,
    plan,
    round(cost_eur, 2) as cost_eur,
    round(customers, 1) as customers,
    round(cost_eur / customers, 2) as blended_cac,
    round(gross_profit_180d, 2) as gross_profit_180d,
    round(gross_profit_180d - cost_eur, 2) as profit_after_marketing_180d,
    round(gross_profit_180d / cost_eur, 2) as roi_180,
    cost_eur / customers <= {{ var("goal_blended_cac") }} as meets_cac_goal
from plans
