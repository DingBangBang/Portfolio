select
    date, channel, ad_type, spend, conversions, clicks,
    case when spend > 0 then conversions / spend end as conversions_per_dollar
from {{ ref('stg_ads_spend') }}
order by date, channel
