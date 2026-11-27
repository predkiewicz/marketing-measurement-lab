-- Orders that arrived more than once in the raw feed (purchase tag fired twice).
-- Revenue at risk = what a naive sum over the raw feed would overstate.
select
    order_id,
    count(*) as events,
    (count(*) - 1) * max(revenue_eur) as revenue_overstated_eur
from {{ ref('raw_orders') }}
group by order_id
having count(*) > 1
