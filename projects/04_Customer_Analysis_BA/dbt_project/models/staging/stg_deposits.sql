select
    dw_id,
    user_id,
    record_type,
    asset,
    cast(amount as double) as amount,
    status,
    fail_reason,
    cast(created_at as timestamp) as created_at
from {{ source('raw', 'fact_deposit_withdraw') }}
