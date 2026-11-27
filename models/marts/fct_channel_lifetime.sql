-- Lifetime value per decided channel: the observed 180-day gross profit plus the months after it,
-- projected with the shared decay and discounted at discount_rate. The monthly level of months 1-6
-- is the channel's own: (180-day value - first order) / 6. Assumes the value horizon is 180 days.
-- Also: how long until a customer's gross
-- profit covers the channel's incremental CAC, when that takes longer than 180 days.
{% set tail = var("ltv_months") - 6 %}
with value as (
    select channel, {% for d in range(0, 181, 30) %}gross_profit_d{{ d }}{% if not loop.last %}, {% endif %}{% endfor %}
    from {{ ref('fct_channel_value') }}
    union all
    -- the regional campaign's customers are valued at the all-customer average, as in fct_channel_decisions
    select 'regional_campaign', {% for d in range(0, 181, 30) %}avg(gross_profit_d{{ d }}){% if not loop.last %}, {% endif %}{% endfor %}
    from {{ ref('fct_customer_value') }}
),

k as (select generated_number as k from ({{ dbt.generate_series(tail) }}) as g),

tail_factors as (
    -- sum over the months after 180 days of decay ^ k, discounted to today
    select
        sum(power(d.decay, k.k) / power(1 + {{ var("discount_rate") }}, (6 + k.k) / 12.0)) as factor,
        sum(power(d.decay_low, k.k) / power(1 + {{ var("discount_rate") }}, (6 + k.k) / 12.0)) as factor_low,
        sum(power(d.decay_high, k.k) / power(1 + {{ var("discount_rate") }}, (6 + k.k) / 12.0)) as factor_high
    from {{ ref('fct_ltv_decay') }} as d
    cross join k
),

base as (
    select
        dec.channel,
        dec.cac_incremental,
        dec.roi_180,
        dec.decision,
        {% for d in range(0, 181, 30) %}v.gross_profit_d{{ d }},{% endfor %}
        (v.gross_profit_d180 - v.gross_profit_d0) / 6 as monthly_level
    from {{ ref('fct_channel_decisions') }} as dec
    inner join value as v on v.channel = dec.channel
),

payback as (
    -- first month (up to ltv_months) in which cumulative, undiscounted gross profit covers incremental
    -- CAC: observed values for months 1-6, the projection after that
    select b.channel, min(m.month) as payback_month
    from base as b
    cross join (select generated_number as month from ({{ dbt.generate_series(var("ltv_months")) }}) as g) as m
    cross join {{ ref('fct_ltv_decay') }} as d
    where case
        {% for mo in range(1, 7) %}when m.month = {{ mo }} then b.gross_profit_d{{ mo * 30 }}
        {% endfor %}        else b.gross_profit_d180 + b.monthly_level * d.decay * (1 - power(d.decay, m.month - 6)) / (1 - d.decay)
    end >= b.cac_incremental
    group by b.channel
)

select
    b.channel,
    b.decision,
    round(b.gross_profit_d180, 2) as gross_profit_180d,
    round(b.gross_profit_d180 + b.monthly_level * t.factor, 2) as ltv,
    round(b.gross_profit_d180 + b.monthly_level * t.factor_low, 2) as ltv_low,
    round(b.gross_profit_d180 + b.monthly_level * t.factor_high, 2) as ltv_high,
    round(b.cac_incremental, 2) as cac_incremental,
    round(b.roi_180, 2) as roi_180,
    -- same added customers, valued over their lifetime instead of 180 days
    round(b.roi_180 * (b.gross_profit_d180 + b.monthly_level * t.factor) / b.gross_profit_d180, 2) as roi_lifetime,
    p.payback_month
from base as b
cross join tail_factors as t
left join payback as p on p.channel = b.channel
