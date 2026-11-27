-- Attributed revenue must equal the revenue of orders that have a path: the models
-- move credit between channels, they never create or lose money. Returns a row on mismatch.
with attributed as (
    select
        sum(revenue_eur * last_click_weight) as last_click,
        sum(revenue_eur * position_based_weight) as position_based
    from {{ ref('fct_attribution') }}
),

orders as (
    select sum(revenue_eur) as revenue
    from {{ ref('stg_orders') }}
    where order_id in (select order_id from {{ ref('fct_attribution') }})
)

select *
from attributed cross join orders
where abs(last_click - revenue) > 0.01
    or abs(position_based - revenue) > 0.01
