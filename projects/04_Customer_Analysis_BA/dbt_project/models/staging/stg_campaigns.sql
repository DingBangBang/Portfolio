select
    campaign_id,
    name,
    channel,
    cast(start_time as timestamp) as start_time,
    cast(end_time as timestamp) as end_time,
    cast(budget as double) as budget,
    reward_type
from {{ source('raw', 'fact_campaigns') }}
