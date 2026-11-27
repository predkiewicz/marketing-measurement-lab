-- The plan moves money, it does not create it: new budget = old budget (recomputed from the books:
-- ad spend plus affiliate commission) - what STOP channels freed + what the allocation hands out.
-- Whether the allocation itself is right is assert_allocation_optimal's job. Returns a row on mismatch.
with books as (
    select
        (select sum(spend_eur) from {{ ref('raw_ad_spend') }})
          + (select sum(revenue_eur * last_click_weight) * {{ var("affiliate_fee") }}
             from {{ ref('fct_attribution') }} where channel = 'affiliate') as cost_eur
),

freed as (
    select coalesce(sum(cost_eur), 0) as eur
    from {{ ref('fct_channel_decisions') }}
    where decision = 'STOP' and channel != 'regional_campaign'
),

received as (
    select coalesce(sum(allocated_eur), 0) as eur from {{ ref('fct_budget_allocation') }}
)

select p.plan, p.cost_eur
from {{ ref('fct_budget_scenario') }} as p
cross join books as b
where (p.sort = 1 and abs(p.cost_eur - b.cost_eur) > 0.01)
   or (p.sort = 2 and abs(p.cost_eur - (b.cost_eur - (select eur from freed) + (select eur from received))) > 0.01)
