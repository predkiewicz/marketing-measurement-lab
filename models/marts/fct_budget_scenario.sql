-- What the decisions do to the always-on budget (attribution period). STOP channels lose their cost
-- and only their INCREMENTAL customers; the freed budget moves to SCALE channels in proportion to
-- their cost, buying customers at incremental CAC x (1 + scale_cost_premium), because the next euro
-- in a channel is less efficient than the average one. TEST channels stay as they are.
-- The regional campaign is a separate budget and not part of this plan.
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

gains as (
    select
        sum(m.freed_eur * d.cost_eur / m.scale_cost) as allocated_eur,
        sum(m.freed_eur * d.cost_eur / m.scale_cost / (d.cac_incremental * (1 + {{ var("scale_cost_premium") }}))) as customers_gained,
        sum(m.freed_eur * d.cost_eur / m.scale_cost / (d.cac_incremental * (1 + {{ var("scale_cost_premium") }}))
            * d.gross_profit_per_customer_180d) as profit_gained
    from d
    cross join moves as m
    where d.decision = 'SCALE'
),

plans as (
    select 1 as sort, 'Current plan' as plan, cost_eur, customers, gross_profit_180d from current_plan
    union all
    select 2, 'After decisions: stop, reallocate to scale',
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
    round(gross_profit_180d / cost_eur, 2) as roi_180,
    cost_eur / customers <= {{ var("goal_blended_cac") }} as meets_cac_goal
from plans
