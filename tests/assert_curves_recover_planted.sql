-- The generator plants each channel's elasticity (curve_planted_elasticity). Every fitted interval
-- must contain it. Returns failing channels.
{% set planted = var("curve_planted_elasticity") %}
select channel, elasticity_low, elasticity, elasticity_high
from {{ ref('fct_response_curves') }}
where
{% for channel, value in planted.items() %}
    (channel = '{{ channel }}' and not ({{ value }} between elasticity_low and elasticity_high))
    {% if not loop.last %}or{% endif %}
{% endfor %}
