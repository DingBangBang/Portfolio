select
    cast(period as date) as period,
    step,
    cast(user_cnt as bigint) as user_cnt,
    cast(prev_step_cnt as bigint) as prev_step_cnt,
    cast(step_cvr as double) as step_cvr
from {{ source('raw', 'fact_funnel_snapshot') }}
