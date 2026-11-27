-- The generator plants how fast repeat buying fades after month 6 (ltv_planted_decay). The fitted
-- interval must contain it. Returns a row on failure.
select *
from {{ ref('fct_ltv_decay') }}
where not ({{ var("ltv_planted_decay") }} between decay_low and decay_high)
