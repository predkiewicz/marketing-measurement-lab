-- Consent modelling must get the channel numbers back close to the truth the simulation knows:
-- every paid channel within 10%, closer than the consent-only view, and never more orders than
-- exist (the leftover 'unattributed' cannot go below zero). Returns one row per breach.
select channel, 'modelled more than 10% off' as breach
from {{ ref('fct_consent_impact') }}
where decision_true is not null and abs(modelled_error) > 0.10
union all
select channel, 'modelling does not beat consent-only'
from {{ ref('fct_consent_impact') }}
where decision_true is not null and abs(modelled_error) >= abs(observed_error)
union all
select channel, 'modelling claims more orders than exist'
from {{ ref('fct_consent_impact') }}
where channel = 'unattributed' and customers_modelled < 0
