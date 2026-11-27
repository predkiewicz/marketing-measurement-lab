-- Customer value must rest on the books: total 180-day gross profit equals margin x (first orders
-- + repeat orders within the horizon), recomputed here from the sources. Returns a row on mismatch.
with model as (
    select sum(gross_profit_d{{ var("value_horizon_days") }}) as gross_profit from {{ ref('fct_customer_value') }}
),

books as (
    select {{ var("gross_margin") }} * (
        (select sum(revenue_eur) from {{ ref('stg_orders') }})
        + (select sum(r.revenue_eur)
           from {{ ref('raw_repeat_orders') }} as r
           inner join {{ ref('stg_orders') }} as o on o.order_id = r.first_order_id
           where {{ dbt.datediff('o.order_ts', 'r.order_ts', 'day') }} <= {{ var("value_horizon_days") }})
    ) as gross_profit
)

select * from model cross join books
where abs(model.gross_profit - books.gross_profit) > 1
