-- One row per tracked marketing touchpoint (ad click, email click, organic visit).
-- Passed through unchanged; click injection is flagged in qa_click_injection, not removed here.
select touchpoint_id, user_id, channel, touch_ts
from {{ ref('raw_touchpoints') }}
