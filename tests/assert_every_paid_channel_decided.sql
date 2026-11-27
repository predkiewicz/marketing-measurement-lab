-- Every channel that costs money gets a decision. Returns channels without one.
select channel
from {{ ref('fct_channel_cac') }}
where cost_eur > 0
    and channel not in (select channel from {{ ref('fct_channel_decisions') }})
union all
-- and every decided channel has a cash line
select channel
from {{ ref('fct_channel_decisions') }}
where channel not in (select channel from {{ ref('fct_channel_cashflow') }})
