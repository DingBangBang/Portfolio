select
    cast(date as date) as date,
    platform,
    cast(followers as bigint) as followers,
    cast(engagements as bigint) as engagements,
    cast(reach as bigint) as reach,
    cast(posting_cnt as integer) as posting_cnt
from {{ source('raw', 'fact_social_metrics') }}
