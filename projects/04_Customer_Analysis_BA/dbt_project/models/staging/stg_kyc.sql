select
    kyc_id,
    user_id,
    kyc_type,
    region as kyc_region,
    status as kyc_status,
    cast(submit_time as timestamp) as submit_time,
    cast(finish_time as timestamp) as finish_time
from {{ source('raw', 'dim_kyc') }}
