select
    test_id,
    user_id,
    variant,
    cast(assigned_at as timestamp) as assigned_at,
    cast(converted as integer) as converted
from {{ source('raw', 'fact_ab_assignments') }}
