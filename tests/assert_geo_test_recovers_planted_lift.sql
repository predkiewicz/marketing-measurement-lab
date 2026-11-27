-- The generator plants a known effect (geo_planted_lift). The readout's interval must contain it,
-- otherwise the estimator is biased or its uncertainty too narrow. Returns a row on failure.
select *
from {{ ref('fct_geo_test') }}
where not (lift_low <= {{ var("geo_planted_lift") }} and {{ var("geo_planted_lift") }} <= lift_high)
