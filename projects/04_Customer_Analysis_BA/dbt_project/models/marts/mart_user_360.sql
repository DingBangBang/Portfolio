with f as (select * from {{ ref('int_user_funnel') }}),
r as (select * from {{ ref('int_user_rfm') }}),
l as (select * from {{ ref('stg_ltv') }}),
t as (
    select user_id, string_agg(tag, ',' order by tag) as tags
    from {{ ref('stg_tags') }} group by 1
)
select
    f.user_id, f.register_time, f.register_date, f.register_channel,
    f.register_device_type, f.kyc_area, f.kyc_type, f.is_robot,
    f.kyc_status, f.kyc_finish_time, f.first_deposit_time, f.first_trade_time,
    f.is_kyc, f.is_deposited, f.is_trader, f.tx_cnt, f.gmv, f.revenue,
    r.recency_days, r.frequency, r.monetary, r.r_score, r.f_score, r.m_score,
    r.rfm_score, r.rfm_segment,
    l.ltv_30d, l.ltv_90d, l.churn_90d, t.tags
from f
left join r on f.user_id = r.user_id
left join l on f.user_id = l.user_id
left join t on f.user_id = t.user_id
