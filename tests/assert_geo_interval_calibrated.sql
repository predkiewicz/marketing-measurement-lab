-- The readout's interval must keep false alarms near 5%: applied to the 8,008 placebo sets, where
-- nothing happened, the standard error it uses may call at most 7% of them significant. An interval
-- that treats days as independent calls about 20% significant here. Returns a row on failure.
with used as (
    -- the standard error the readout actually used, recovered from its interval
    select (ln(1 + lift_high) - ln(1 + lift_low)) / (2 * {{ var("geo_ci_z") }}) as se
    from {{ ref('fct_geo_test') }}
)

select avg(case when abs(p.lift_log) > {{ var("geo_ci_z") }} * u.se then 1.0 else 0 end) as false_alarm_rate
from {{ ref('fct_geo_placebo') }} as p
cross join used as u
having avg(case when abs(p.lift_log) > {{ var("geo_ci_z") }} * u.se then 1.0 else 0 end) > 0.07
