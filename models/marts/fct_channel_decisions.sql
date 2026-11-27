-- One decision per paid channel and campaign: SCALE, TEST or STOP, from the goals in dbt_project.yml.
--
-- roi_180 = 180-day gross profit of the customers a channel ADDED / what the channel cost.
-- Above 1, the channel pays back within the horizon. Each channel's ROI comes with a best and a worst
-- case from the incrementality interval, and the rule only speaks when the interval allows it:
--   SCALE: roi_180 >= scale_min_roi, and still >= 1 in the worst case
--   STOP:  roi_180 < stop_max_roi even in the best case
--   TEST:  everything else; the data cannot yet back a SCALE or a STOP
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
    -- first day on which a customer's cumulative gross profit covers the incremental CAC
    case
        {% for d in range(0, var("value_horizon_days") + 1, 30) %}
        when gross_profit_d{{ d }} >= cac_incremental then {{ d }}
        {% endfor %}
    end as payback_days,
    incrementality_verdict,
    coalesce(q.flagged_clicks, 0) as flagged_fraud_clicks,
    case
        when roi_180 >= {{ var("scale_min_roi") }} and roi_180_worst >= 1 then 'SCALE'
        when roi_180_best < {{ var("stop_max_roi") }} then 'STOP'
        else 'TEST'
    end as decision,
    case
        when roi_180 >= {{ var("scale_min_roi") }} and roi_180_worst >= 1
            then 'Pays back within the horizon even in the worst case; room to grow'
        when roi_180_best < {{ var("stop_max_roi") }}
            then 'Does not pay back within the horizon even in the best case'
        when roi_180_worst < 1 and roi_180_best >= {{ var("scale_min_roi") }}
            then 'Interval too wide: could be the best or a losing channel; sharpen the test'
        when roi_180 >= 1
            then 'Pays back, but below the scale threshold or not in the worst case; test changes'
        else 'Likely loses money, but the best case pays back; test before stopping'
    end as reason
from scored
left join (
    -- fraud findings travel with the decision: a channel with flagged clicks needs a dispute too
    select channel, count(*) as flagged_clicks from {{ ref('qa_click_injection') }} group by channel
) as q using (channel)
