-- Repeat orders per customer by month since the first order (30-day months), counting in each month
-- only the customers who have been observed that long by observed_until. Without that, recent
-- cohorts would count as customers who stopped buying, when they simply have not had the time yet.
with months as (
    select generated_number as month from ({{ dbt.generate_series(12) }}) as g
),

exposed as (
    select m.month, o.order_id
    from months as m
    cross join {{ ref('stg_orders') }} as o
    where {{ dbt.dateadd('day', 'm.month * 30', 'o.order_ts') }} <= cast('{{ var("observed_until") }}' as timestamp)
),

repeats as (
    select
        r.first_order_id as order_id,
        greatest(1, cast(ceil({{ dbt.datediff('o.order_ts', 'r.order_ts', 'day') }} / 30.0) as integer)) as month
    from {{ ref('raw_repeat_orders') }} as r
    inner join {{ ref('stg_orders') }} as o on o.order_id = r.first_order_id
)

select
    e.month,
    count(distinct e.order_id) as customers_observed,
    count(r.order_id) as repeat_orders,
    count(r.order_id) * 1.0 / count(distinct e.order_id) as orders_per_customer
from exposed as e
left join repeats as r on r.order_id = e.order_id and r.month = e.month
group by e.month
