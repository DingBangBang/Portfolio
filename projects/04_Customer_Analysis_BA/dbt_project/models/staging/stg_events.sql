select
    event_id,
    user_id,
    cast(event_time as timestamp) as event_time,
    event_name,
    page,
    module_id,
    session_id,
    device
from {{ source('raw', 'fact_events') }}
