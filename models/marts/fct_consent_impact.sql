-- What consent loss does to the channel numbers, and how far modelling gets them back.
--   true:     full journeys (only a simulation has them)
--   observed: consented journeys only, what a real setup reports
--   modelled: each observed order weighted by 1 / consent rate of the channel its journey started
--             from. The rate comes from the banner's aggregate counts per landing channel, which
--             hold no user data. Unconsented orders are pulled back out of 'unattributed'.
-- Holdout, budget-step and geo tests count backend orders, so consent does not touch them; only
-- attribution-based numbers move. Decisions are recomputed on each view with the same rule.
with rates as (
    select landing_channel as channel, sum(accepted) * 1.0 / sum(banner_views) as consent_rate
    from {{ ref('raw_consent_banner') }}
    group by landing_channel
),

journey_start as (
    -- the channel each observed journey started from decides its weight
    select order_id, channel as start_channel
    from {{ ref('fct_attribution_consented') }}
    where touch_position = 1 and channel != 'unattributed'
),

observed as (
    select
        a.channel,
        sum(a.position_based_weight) as customers_observed,
        sum(a.position_based_weight / coalesce(r.consent_rate, 1)) as customers_modelled
    from {{ ref('fct_attribution_consented') }} as a
    left join journey_start as j on j.order_id = a.order_id
    left join rates as r on r.channel = j.start_channel
    group by a.channel
),

truth as (
    select channel, sum(position_based_weight) as customers_true
    from {{ ref('fct_attribution') }}
    group by channel
),

channels as (
    select
        t.channel,
        t.customers_true,
        o.customers_observed,
        case when t.channel = 'unattributed'
            -- what is left of all orders once the modelled channels have taken theirs back
            then (select count(*) from {{ ref('stg_orders') }})
                 - (select sum(customers_modelled) from observed where channel != 'unattributed')
            else o.customers_modelled
        end as customers_modelled,
        r.consent_rate
    from truth as t
    left join observed as o on o.channel = t.channel
    left join rates as r on r.channel = t.channel
),

views as (
    select
        c.*,
        d.cost_eur,
        d.roi_180,
        d.roi_180_worst,
        d.roi_180_best,
        d.elasticity,
        d.decision as decision_true,
        c.customers_observed / c.customers_true as ratio_observed,
        c.customers_modelled / c.customers_true as ratio_modelled
    from channels as c
    left join {{ ref('fct_channel_decisions') }} as d on d.channel = c.channel
)

select
    channel,
    round(consent_rate, 3) as consent_rate,
    round(customers_true, 1) as customers_true,
    round(customers_observed, 1) as customers_observed,
    round(customers_modelled, 1) as customers_modelled,
    round(ratio_observed - 1, 3) as observed_error,
    round(ratio_modelled - 1, 3) as modelled_error,
    round(nullif(cost_eur, 0) / customers_true, 2) as cac_true,
    round(nullif(cost_eur, 0) / customers_observed, 2) as cac_observed,
    round(nullif(cost_eur, 0) / customers_modelled, 2) as cac_modelled,
    round(roi_180, 2) as roi_true,
    round(roi_180 * ratio_observed, 2) as roi_observed,
    round(roi_180 * ratio_modelled, 2) as roi_modelled,
    decision_true,
    case when decision_true is not null then
        {{ decision('elasticity * roi_180 * ratio_observed', 'roi_180 * ratio_observed',
                    'roi_180_worst * ratio_observed', 'roi_180_best * ratio_observed') }}
    end as decision_observed,
    case when decision_true is not null then
        {{ decision('elasticity * roi_180 * ratio_modelled', 'roi_180 * ratio_modelled',
                    'roi_180_worst * ratio_modelled', 'roi_180_best * ratio_modelled') }}
    end as decision_modelled
from views
