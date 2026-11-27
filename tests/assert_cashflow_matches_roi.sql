-- The cash line must end where the ROI says: net cash per 1,000 at the horizon = 1,000 x (ROI - 1).
-- Returns channels where the two disagree by more than rounding.
select c.channel, c.net_cash_per_1000_eur, d.roi_180
from {{ ref('fct_channel_cashflow') }} as c
inner join {{ ref('fct_channel_decisions') }} as d on d.channel = c.channel
where c.day = {{ var("value_horizon_days") }}
    and abs(c.net_cash_per_1000_eur - 1000 * (d.roi_180 - 1)) > 6
