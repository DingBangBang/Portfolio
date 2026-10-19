with users as (
    select * from {{ ref('stg_users') }}
),
kyc as (
    select user_id, kyc_status, finish_time
    from {{ ref('stg_kyc') }}
),
dep as (
    select user_id, min(created_at) as first_deposit_time
    from {{ ref('stg_deposits') }}
    where record_type in ('DEPOSIT', 'COIN_IN') and status = 'SUCCESS'
    group by 1
),
trade as (
    select user_id, min(tx_time) as first_trade_time,
           count(*) as tx_cnt, sum(quote_amt) as gmv, sum(fee) as revenue
    from {{ ref('stg_transactions') }}
    group by 1
)
select
    u.user_id,
    u.register_time,
    u.register_date,
    u.register_channel,
    u.register_device_type,
    u.kyc_area,
    u.kyc_type,
    u.is_robot,
    k.kyc_status,
    k.finish_time as kyc_finish_time,
    d.first_deposit_time,
    t.first_trade_time,
    case when k.kyc_status = 'SUCCESS' then 1 else 0 end as is_kyc,
    case when d.first_deposit_time is not null then 1 else 0 end as is_deposited,
    case when t.first_trade_time is not null then 1 else 0 end as is_trader,
    coalesce(t.tx_cnt, 0) as tx_cnt,
    coalesce(t.gmv, 0) as gmv,
    coalesce(t.revenue, 0) as revenue
from users u
left join kyc k on u.user_id = k.user_id
left join dep d on u.user_id = d.user_id
left join trade t on u.user_id = t.user_id
