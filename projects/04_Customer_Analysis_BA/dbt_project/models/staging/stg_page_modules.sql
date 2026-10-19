select
    cast(date as date) as date,
    page,
    module_id,
    cast(module_area_pct as double) as module_area_pct,
    cast(impressions as bigint) as impressions,
    cast(clicks as bigint) as clicks
from {{ source('raw', 'fact_page_modules') }}
