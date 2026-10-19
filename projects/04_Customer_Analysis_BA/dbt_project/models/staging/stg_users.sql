select
    user_id,
    cast(register_time as timestamp) as register_time,
    cast(date_trunc('day', register_time) as date) as register_date,
    register_device_type,
    register_channel,
    kyc_area,
    kyc_type,
    cast(is_robot as boolean) as is_robot
from {{ source('raw', 'dim_users') }}
