-- Funnel counts must be non-increasing across steps for every period.
with p as (
    select
        period,
        max(case when step = 'visit' then user_cnt end) as visit_cnt,
        max(case when step = 'register' then user_cnt end) as register_cnt,
        max(case when step = 'kyc' then user_cnt end) as kyc_cnt,
        max(case when step = 'deposit' then user_cnt end) as deposit_cnt,
        max(case when step = 'trade' then user_cnt end) as trade_cnt
    from {{ ref('mart_funnel_daily') }}
    group by 1
)
select *
from p
where not (
    visit_cnt >= register_cnt
    and register_cnt >= kyc_cnt
    and kyc_cnt >= deposit_cnt
    and deposit_cnt >= trade_cnt
)
