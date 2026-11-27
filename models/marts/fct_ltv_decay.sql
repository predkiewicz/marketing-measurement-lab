-- How fast repeat buying fades after the first six months, shared by all channels (channels differ
-- in how often their customers buy, which the 180-day value already measures, not in how fast they
-- stop). Fit: ln(orders per customer in month t / months-1-6 level) = (t - 6) x ln(decay), a line
-- through the origin over the months after 6 that at least min_customers have been observed for.
{% set min_customers = 300 %}
with level as (
    select avg(orders_per_customer) as level from {{ ref('fct_retention_monthly') }} where month <= 6
),

points as (
    select r.month - 6 as x, ln(r.orders_per_customer / l.level) as y
    from {{ ref('fct_retention_monthly') }} as r
    cross join level as l
    where r.month > 6 and r.customers_observed >= {{ min_customers }} and r.orders_per_customer > 0
),

fit as (
    select count(*) as months, sum(x * y) / sum(x * x) as slope, sum(x * x) as sxx from points
),

se as (
    select f.months, f.slope, sqrt(sum(power(p.y - f.slope * p.x, 2)) / (f.months - 1) / f.sxx) as slope_se
    from fit as f
    cross join points as p
    group by f.months, f.slope, f.sxx
)

select
    months,
    round(exp(slope), 3) as decay,
    -- 95% t value for months - 1 degrees of freedom; few months, so the interval is honest about it
    round(exp(slope - t.value * slope_se), 3) as decay_low,
    round(least(exp(slope + t.value * slope_se), 0.999), 3) as decay_high
from se
cross join (
    select case (select months - 1 from fit)
        when 1 then 12.706 when 2 then 4.303 when 3 then 3.182 when 4 then 2.776 when 5 then 2.571 else 2.447
    end as value
) as t
