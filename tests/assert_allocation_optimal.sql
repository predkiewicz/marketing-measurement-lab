-- The freed budget must be split so that no euro could be moved to earn more (equal marginal ROI).
-- Checked from the allocation's own result, condition by condition. Returns one row per breach.
with a as (
    select
        *,
        allocated_eur > 0.01 as funded,
        spend_multiplier < profitable_spend_multiplier - 0.001 as below_cap
    from {{ ref('fct_budget_allocation') }}
),

freed as (
    select coalesce(sum(cost_eur), 0) as eur
    from {{ ref('fct_channel_decisions') }}
    where decision = 'STOP' and channel != 'regional_campaign'
),

totals as (
    select
        (select eur from freed) as freed_eur,
        coalesce(sum(allocated_eur), 0) as allocated_eur,
        min(case when funded then marginal_roi_after end) as lowest_funded_marginal
    from a
)

select 'spends more than was freed' as breach, null as channel from totals
where allocated_eur > freed_eur + 0.01
union all
select 'funded below a marginal ROI of 1', channel from a
where funded and marginal_roi_after < 0.995
union all
select 'funded channels end at different marginal ROI', min(channel) from a
where funded and below_cap
having max(marginal_roi_after) - min(marginal_roi_after) > 0.01
union all
select 'unfunded channel has a better next euro than a funded one', a.channel
from a cross join totals as t
where not a.funded and a.marginal_roi_after > t.lowest_funded_marginal + 0.01
union all
select 'money left unspent while a channel still earns more than 1', a.channel
from a cross join totals as t
where t.freed_eur - t.allocated_eur > 0.005 * t.freed_eur
    and a.below_cap and a.marginal_roi_after > 1.005
