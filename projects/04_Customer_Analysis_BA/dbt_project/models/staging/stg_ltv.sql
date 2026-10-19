select
    user_id,
    cohort,
    cast(ltv_30d as double) as ltv_30d,
    cast(ltv_90d as double) as ltv_90d,
    cast(churn_90d as integer) as churn_90d
from {{ source('raw', 'fact_ltv_labels') }}
