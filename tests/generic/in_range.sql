{% test in_range(model, column_name, min_value=none, max_value=none) %}
-- Domain bounds on intake: a negative spend or a multiplier outside the test design fails here,
-- before it moves a decision. NULLs are left to not_null.
select {{ column_name }}
from {{ model }}
where {% if min_value is not none %}{{ column_name }} < {{ min_value }}{% endif %}
    {% if min_value is not none and max_value is not none %} or {% endif %}
    {% if max_value is not none %}{{ column_name }} > {{ max_value }}{% endif %}
{% endtest %}
