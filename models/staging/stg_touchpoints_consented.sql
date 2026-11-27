-- What a real setup sees: touchpoints of users who accepted the consent banner. Users who declined
-- are invisible to tracking; their orders still reach the shop's backend (stg_orders) and show up
-- as 'unattributed'. raw_consent exists only in this simulation, to know which journeys to hide.
select t.*
from {{ ref('stg_touchpoints') }} as t
inner join {{ ref('raw_consent') }} as c on c.user_id = t.user_id
where c.consented
