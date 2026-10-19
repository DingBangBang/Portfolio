select
    tp_id,
    user_id,
    cast(touch_time as timestamp) as touch_time,
    channel,
    campaign_id,
    cast(position_in_path as integer) as position_in_path,
    cast(converted as integer) as converted
from {{ source('raw', 'fact_touchpoints') }}
