-- The generator plants each channel's true incrementality (holdout_planted_incrementality).
-- Every holdout readout's interval must contain it. Returns failing channels.
{% set planted = var("holdout_planted_incrementality") %}
select channel, incrementality_low, incrementality, incrementality_high
from {{ ref('fct_channel_incrementality') }}
where
{% for channel, value in planted.items() %}
    (channel = '{{ channel }}' and not ({{ value }} between incrementality_low and incrementality_high))
    {% if not loop.last %}or{% endif %}
{% endfor %}
