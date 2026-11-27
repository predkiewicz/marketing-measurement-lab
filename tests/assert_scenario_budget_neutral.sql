-- The plan moves money, it does not create it: the new budget equals the old one minus what STOP
-- channels freed plus what SCALE channels received, recomputed here from the decisions and the
-- profitable-spend cap. Returns a row on mismatch.
with d as (
    select * from {{ ref('fct_channel_decisions') }} where channel != 'regional_campaign'
),

freed as (
    select coalesce(sum(cost_eur), 0) as eur from d where decision = 'STOP'
),

received as (
    select coalesce(sum(least(
        (select eur from freed) * cost_eur / (select sum(cost_eur) from d where decision = 'SCALE'),
        cost_eur * (profitable_spend_multiplier - 1))), 0) as eur
    from d where decision = 'SCALE'
)

select *
from {{ ref('fct_budget_scenario') }}
where sort = 2
    and abs(cost_eur - ((select cost_eur from {{ ref('fct_budget_scenario') }} where sort = 1)
        - (select eur from freed) + (select eur from received))) > 0.01
