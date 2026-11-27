{% test unique_combination(model, columns) %}
-- A seed's key spans several columns: one row per combination, or a duplicate is double-counted.
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
