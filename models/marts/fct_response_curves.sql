-- Response curve per paid channel from its budget-step test: how the customers a channel adds grow
-- with spend. Model: added = added_today x multiplier ^ elasticity. Elasticity 1 = every euro works
-- as well as the last; below 1 = each extra euro buys fewer customers (diminishing returns).
--
-- Each week, the regions with the channel switched off (multiplier 0) give the baseline. Added
-- customers at a spend level = conversions per million people minus that week's baseline, averaged
-- over the weeks. The elasticity is the slope of ln(added) on ln(multiplier) across spend levels.
with cells as (
    select
        s.test_channel,
        s.week,
        s.spend_multiplier,
        sum(s.conversions) / sum(r.population_m) as conversions_per_m
    from {{ ref('raw_budget_steps') }} as s
    inner join {{ ref('raw_geo_regions') }} as r on r.region_code = s.region_code
    group by s.test_channel, s.week, s.spend_multiplier
),

added as (
    select
        c.test_channel,
        c.spend_multiplier,
        avg(c.conversions_per_m - b.conversions_per_m) as added_per_m
    from cells as c
    inner join cells as b
        on b.test_channel = c.test_channel and b.week = c.week and b.spend_multiplier = 0
    where c.spend_multiplier > 0
    group by c.test_channel, c.spend_multiplier
),

points as (
    select test_channel, ln(spend_multiplier) as x, ln(added_per_m) as y
    from added
    where added_per_m > 0  -- a level with no measurable effect cannot sit on a log curve
),

fit as (
    select
        test_channel,
        count(*) as levels,
        covar_samp(x, y) / var_samp(x) as elasticity,
        avg(y) - covar_samp(x, y) / var_samp(x) * avg(x) as intercept,
        var_samp(x) * (count(*) - 1) as sxx
    from points
    group by test_channel
),

residuals as (
    select f.test_channel, sum(power(p.y - (f.intercept + f.elasticity * p.x), 2)) as sse
    from fit as f
    inner join points as p on p.test_channel = f.test_channel
    group by f.test_channel
)

select
    f.test_channel as channel,
    f.levels,
    round(f.elasticity, 3) as elasticity,
    round(f.elasticity - {{ var("curve_ci_t") }} * sqrt(r.sse / (f.levels - 2) / f.sxx), 3) as elasticity_low,
    round(f.elasticity + {{ var("curve_ci_t") }} * sqrt(r.sse / (f.levels - 2) / f.sxx), 3) as elasticity_high,
    round(exp(f.intercept), 2) as added_per_m_week_at_today
from fit as f
inner join residuals as r on r.test_channel = f.test_channel
