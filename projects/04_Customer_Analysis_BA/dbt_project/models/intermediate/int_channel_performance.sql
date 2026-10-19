with spend as (
    select channel,
           sum(spend) as ad_spend,
           sum(clicks) as ad_clicks,
           sum(conversions) as ad_conversions
    from {{ ref('stg_ads_spend') }}
    group by 1
),
users as (
    select register_channel as channel, count(*) as signups
    from {{ ref('stg_users') }}
    group by 1
),
funnel as (
    select
        u.register_channel as channel,
        sum(f.is_kyc) as kyc_users,
        sum(f.is_deposited) as depositors,
        sum(f.is_trader) as traders,
        sum(f.revenue) as revenue
    from {{ ref('int_user_funnel') }} f
    join {{ ref('stg_users') }} u on f.user_id = u.user_id
    group by 1
)
select
    coalesce(s.channel, u.channel, f.channel) as channel,
    coalesce(s.ad_spend, 0) as ad_spend,
    coalesce(s.ad_clicks, 0) as ad_clicks,
    coalesce(s.ad_conversions, 0) as ad_conversions,
    coalesce(u.signups, 0) as signups,
    coalesce(f.kyc_users, 0) as kyc_users,
    coalesce(f.depositors, 0) as depositors,
    coalesce(f.traders, 0) as traders,
    coalesce(f.revenue, 0) as revenue,
    case when coalesce(u.signups, 0) > 0 then coalesce(s.ad_spend, 0) / u.signups else null end as cac,
    case when coalesce(f.depositors, 0) > 0 then coalesce(s.ad_spend, 0) / f.depositors else null end as cpa,
    case when coalesce(s.ad_spend, 0) > 0 then coalesce(f.revenue, 0) / s.ad_spend else null end as roi,
    case when coalesce(u.signups, 0) > 0 then 1.0 * coalesce(f.depositors, 0) / u.signups else null end as deposit_rate
from spend s
full outer join users u on s.channel = u.channel
full outer join funnel f on coalesce(s.channel, u.channel) = f.channel
