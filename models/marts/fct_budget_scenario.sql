-- What the decisions do to the always-on budget (attribution period).
--   STOP channels lose their cost and only their ADDED customers.
--   SCALE channels take the freed budget as fct_budget_allocation splits it: equal marginal ROI,
--   each channel at most up to its profitable spend. Money no channel can use profitably is not spent.
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
        sum(case when decision = 'STOP' then customers_incremental * gross_profit_per_customer_180d else 0 end) as profit_lost
    from d
),

gains as (
    select
        sum(allocated_eur) as allocated_eur,
        sum(customers_gained) as customers_gained,
        sum(profit_gained) as profit_gained
    from {{ ref('fct_budget_allocation') }}
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
