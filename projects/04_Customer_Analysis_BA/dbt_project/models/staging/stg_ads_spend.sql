select
    cast(date as date) as date,
    channel,
    ad_type,
    cast(impressions as bigint) as impressions,
    cast(clicks as bigint) as clicks,
    cast(spend as double) as spend,
    cast(cpc as double) as cpc,
    cast(cpa as double) as cpa,
    cast(conversions as bigint) as conversions
from {{ source('raw', 'fact_ads_spend') }}
