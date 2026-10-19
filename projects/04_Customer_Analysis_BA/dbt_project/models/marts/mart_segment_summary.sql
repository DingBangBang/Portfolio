select
    rfm_segment,
    count(*) as users,
    sum(is_deposited) as depositors,
    avg(ltv_30d) as avg_ltv_30d,
    avg(ltv_90d) as avg_ltv_90d,
    sum(revenue) as revenue,
    avg(tx_cnt) as avg_tx_cnt
from {{ ref('mart_user_360') }}
where rfm_segment is not null
group by 1
order by revenue desc
