-- Attributed revenue must equal the revenue of every order in stg_orders: the models move
-- credit between channels (including 'unattributed'), they never create or lose money.
-- Returns a row on mismatch.
with attributed as (
    select
        sum(revenue_eur * last_click_weight) as last_click,
        sum(revenue_eur * position_based_weight) as position_based
    from {{ ref('fct_attribution') }}
),

orders as (
    select sum(revenue_eur) as revenue
    from {{ ref('stg_orders') }}
)

select *
from attributed cross join orders
where abs(last_click - revenue) > 0.01
    or abs(position_based - revenue) > 0.01
