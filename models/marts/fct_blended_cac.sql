-- Blended CAC, the number finance sees, next to the views that explain it. Affiliates look cheap
-- per customer, so they pull blended CAC down. But if most of their customers would have come
-- anyway, removing affiliates removes only the incremental ones, and the commission was paying for
-- customers the business already had.
with c as (
    select
        sum(cost_eur) as cost_all,
        sum(case when channel in ('paid_search', 'paid_social', 'display') then cost_eur end) as cost_paid_media,
        sum(case when channel = 'affiliate' then cost_eur end) as cost_affiliate,
        sum(customers_position_based) as customers_all,
        sum(case when channel in ('paid_search', 'paid_social', 'display') then customers_position_based end) as customers_paid_media,
        sum(case when channel = 'affiliate' then customers_position_based end) as customers_affiliate,
        sum(case when channel = 'affiliate' then customers_incremental end) as customers_affiliate_incremental,
        sum(customers_incremental) as customers_incremental_tested
    from {{ ref('fct_channel_cac') }}
),

views as (
    select 1 as sort, 'Blended: all marketing cost / all customers' as view, cost_all as cost_eur, customers_all as customers from c
    union all
    select 2, 'Paid media only: search, social, display', cost_paid_media, customers_paid_media from c
    union all
    select 3, 'Blended without affiliate, as attributed', cost_all - cost_affiliate, customers_all - customers_affiliate from c
    union all
    select 4, 'Blended without affiliate, incremental: only affiliate''s incremental customers leave', cost_all - cost_affiliate, customers_all - customers_affiliate_incremental from c
    union all
    select 5, 'Incremental: paid media and affiliate cost / customers they added', cost_paid_media + cost_affiliate, customers_incremental_tested from c
)

select sort, view, round(cost_eur, 2) as cost_eur, round(customers, 1) as customers, round(cost_eur / customers, 2) as cac
from views
