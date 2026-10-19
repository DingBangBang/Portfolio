select
    campaign_id,
    user_id,
    cast(join_time as timestamp) as join_time,
    cast(reward_amt as double) as reward_amt,
    cast(is_new_user as integer) as is_new_user
from {{ source('raw', 'bridge_campaign_user') }}
