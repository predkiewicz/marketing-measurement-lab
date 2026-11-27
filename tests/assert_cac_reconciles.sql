-- Blended CAC must rest on the full books: every customer and every euro of cost (ad spend plus
-- the affiliate commission) exactly once. Returns a row on mismatch.
with blended as (
    select cost_eur, customers from {{ ref('fct_blended_cac') }} where sort = 1
),

books as (
    select
        (select sum(spend_eur) from {{ ref('raw_ad_spend') }})
          -- commission recomputed from the attribution table, not read from the model under test
          + (select sum(revenue_eur * last_click_weight) * {{ var("affiliate_fee") }}
             from {{ ref('fct_attribution') }} where channel = 'affiliate') as cost_eur,
        (select count(*) from {{ ref('stg_orders') }}) as customers
)

select *
from blended cross join books
where abs(blended.cost_eur - books.cost_eur) > 0.01
    or abs(blended.customers - books.customers) > 0.01
