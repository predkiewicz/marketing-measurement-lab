-- One decision per paid channel and campaign: SCALE, TEST or STOP, from the goals in dbt_project.yml.
--
-- roi_180 = 180-day gross profit of the customers a channel ADDED / what the channel cost.
-- Above 1, the channel pays back within the horizon. Each channel's ROI comes with a best and a worst
-- case from the incrementality interval, and the rule only speaks when the interval allows it:
--   SCALE: the next euro still pays back (marginal ROI >= 1, from the response curve), and the
--          average still pays back in the worst case
--   STOP:  roi_180 < stop_max_roi even in the best case
--   TEST:  everything else; the data cannot yet back a SCALE or a STOP
--
-- Marginal ROI: with added customers = today x multiplier ^ elasticity, the next euro buys
-- elasticity x (average customers per euro), so marginal ROI = elasticity x roi_180. The spend at
-- which the next euro stops paying back is today x (elasticity x roi_180) ^ (1 / (1 - elasticity)).
-- Channels without a budget-step test (affiliate: paid by commission; the campaign) have no curve
-- and cannot be scaled on this evidence.
with channels as (
    select
        c.channel,
        c.cost_eur,
        c.customers_position_based * i.incrementality as customers_incremental,
        c.customers_position_based * greatest(i.incrementality_low, 0) as customers_incremental_worst,
        c.customers_position_based * least(i.incrementality_high, 1) as customers_incremental_best,
        v.gross_profit_d{{ var("value_horizon_days") }} as gross_profit_per_customer,
        {% for d in range(0, var("value_horizon_days") + 1, 30) %}v.gross_profit_d{{ d }},{% endfor %}
        i.verdict as incrementality_verdict
    from {{ ref('fct_channel_cac') }} as c
    inner join {{ ref('fct_channel_incrementality') }} as i on i.channel = c.channel
    inner join {{ ref('fct_channel_value') }} as v on v.channel = c.channel
),

campaign as (
    -- the regional campaign from the geo test; its customers are valued at the all-customer average
    select
        'regional_campaign' as channel,
        g.campaign_spend_eur as cost_eur,
        g.incremental_conversions as customers_incremental,
        greatest(g.incremental_conversions_low, 0) as customers_incremental_worst,
        g.incremental_conversions_high as customers_incremental_best,
        v.gross_profit_d{{ var("value_horizon_days") }} as gross_profit_per_customer,
        {% for d in range(0, var("value_horizon_days") + 1, 30) %}v.gross_profit_d{{ d }},{% endfor %}
        case when g.is_significant then 'lift confirmed' else 'no confirmed lift' end as incrementality_verdict
    from {{ ref('fct_geo_test') }} as g
    cross join (
        select {% for d in range(0, var("value_horizon_days") + 1, 30) %}avg(gross_profit_d{{ d }}) as gross_profit_d{{ d }}{% if not loop.last %}, {% endif %}{% endfor %}
        from {{ ref('fct_customer_value') }}
    ) as v
),

scored as (
    select
        *,
        cost_eur / nullif(customers_incremental, 0) as cac_incremental,
        customers_incremental * gross_profit_per_customer / cost_eur as roi_180,
        customers_incremental_worst * gross_profit_per_customer / cost_eur as roi_180_worst,
        customers_incremental_best * gross_profit_per_customer / cost_eur as roi_180_best
    from (select * from channels union all select * from campaign) as u
)

select
    channel,
    round(cost_eur, 2) as cost_eur,
    round(customers_incremental, 1) as customers_incremental,
    round(cac_incremental, 2) as cac_incremental,
    round(gross_profit_per_customer, 2) as gross_profit_per_customer_180d,
    round(roi_180_worst, 2) as roi_180_worst,
    round(roi_180, 2) as roi_180,
    round(roi_180_best, 2) as roi_180_best,
    k.elasticity,
    round(k.elasticity * roi_180, 2) as marginal_roi_180,
    -- spend, as a multiple of today, at which the next euro stops paying back; capped at the
    -- highest level the budget-step test covered, because the curve is unknown beyond it
    -- (explicit case: least() skips NULLs in DuckDB, so a channel without a curve would get the cap)
    case when k.elasticity is not null then
        round(least(power(k.elasticity * roi_180, 1 / (1 - k.elasticity)), {{ var("curve_max_multiplier") }}), 2)
    end as profitable_spend_multiplier,
    -- first day on which a customer's cumulative gross profit covers the incremental CAC
    case
        {% for d in range(0, var("value_horizon_days") + 1, 30) %}
        when gross_profit_d{{ d }} >= cac_incremental then {{ d }}
        {% endfor %}
    end as payback_days,
    incrementality_verdict,
    coalesce(q.flagged_clicks, 0) as flagged_fraud_clicks,
    {{ decision('k.elasticity * roi_180', 'roi_180', 'roi_180_worst', 'roi_180_best') }} as decision,
    case
        when k.elasticity * roi_180 >= 1 and roi_180_worst >= 1
            then 'The next euro still pays back, and so does the worst case: grow up to the profitable spend'
        when roi_180_best < {{ var("stop_max_roi") }}
            then 'Does not pay back within the horizon even in the best case'
        when roi_180 >= 1 and k.elasticity * roi_180 < 1
            then 'Pays back on average, but the last euros do not: test a lower budget'
        when roi_180_worst < 1 and roi_180_best >= 1
            then 'Interval too wide: could be a winning or a losing channel; sharpen the test'
        else 'Pays back, but no response curve to size a larger budget: test a budget step'
    end as reason
from scored
left join {{ ref('fct_response_curves') }} as k using (channel)
left join (
    -- fraud findings travel with the decision: a channel with flagged clicks needs a dispute too
    select channel, count(*) as flagged_clicks from {{ ref('qa_click_injection') }} group by channel
) as q using (channel)
