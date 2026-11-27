-- One row per order. The raw feed has duplicate purchase events (tag fired twice);
-- qa_duplicate_orders counts them, this model keeps the first.
select order_id, user_id, order_ts, revenue_eur
from (
    select *,
        row_number() over (partition by order_id order by order_ts) as rn
    from {{ ref('raw_orders') }}
) as o
where rn = 1
