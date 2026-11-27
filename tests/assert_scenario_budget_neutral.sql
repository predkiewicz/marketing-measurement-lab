-- Reallocation moves money, it does not create it: both plans spend the same. Returns a row on mismatch.
select *
from {{ ref('fct_budget_scenario') }}
where abs(cost_eur - (select cost_eur from {{ ref('fct_budget_scenario') }} where sort = 1)) > 0.01
