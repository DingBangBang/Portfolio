with tx as (
    select * from {{ ref('stg_transactions') }}
),
anchor as (
    select max(tx_time) as as_of from tx
),
agg as (
    select user_id,
           max(tx_time) as last_tx,
           count(*) as frequency,
           sum(quote_amt) as monetary,
           sum(fee) as revenue
    from tx
    group by 1
),
scored as (
    select
        a.user_id,
        date_diff('day', a.last_tx, anchor.as_of) as recency_days,
        a.frequency,
        a.monetary,
        a.revenue,
        case when date_diff('day', a.last_tx, anchor.as_of) <= 7 then 5
             when date_diff('day', a.last_tx, anchor.as_of) <= 30 then 4
             when date_diff('day', a.last_tx, anchor.as_of) <= 60 then 3
             when date_diff('day', a.last_tx, anchor.as_of) <= 90 then 2
             else 1 end as r_score,
        case when a.frequency >= 20 then 5
             when a.frequency >= 10 then 4
             when a.frequency >= 5 then 3
             when a.frequency >= 2 then 2
             else 1 end as f_score,
        case when a.monetary >= 5000 then 5
             when a.monetary >= 2000 then 4
             when a.monetary >= 800 then 3
             when a.monetary >= 300 then 2
             else 1 end as m_score
    from agg a cross join anchor
)
select
    *,
    r_score + f_score + m_score as rfm_score,
    case
        when r_score + f_score + m_score >= 13 then 'champions'
        when r_score + f_score + m_score >= 11 then 'loyal'
        when r_score + f_score + m_score >= 9 then 'promising'
        when r_score + f_score + m_score >= 7 then 'need_attention'
        when r_score + f_score + m_score >= 5 then 'at_risk'
        else 'hibernating'
    end as rfm_segment
from scored
