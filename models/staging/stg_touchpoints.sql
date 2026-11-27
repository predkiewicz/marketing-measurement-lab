select touchpoint_id, user_id, channel, touch_ts
from {{ ref('raw_touchpoints') }}
