{% test whole_number(model, column_name) %}
-- Counts load as double on purpose: an integer column would round 136.7 to 137 without a word.
-- Loaded as double, a fractional count is still there to be caught.
select {{ column_name }}
from {{ model }}
where {{ column_name }} != round({{ column_name }})
{% endtest %}
