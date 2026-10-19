with c as (select * from {{ ref('stg_campaigns') }}),
cu as (
    select campaign_id, count(*) as participants, sum(reward_amt) as reward_cost,
           sum(is_new_user) as new_users
    from {{ ref('stg_campaign_users') }} group by 1
),
rev as (
    select cu.campaign_id, sum(f.revenue) as revenue
    from {{ ref('stg_campaign_users') }} cu
    join {{ ref('mart_user_360') }} f on cu.user_id = f.user_id
    group by 1
)
select
    c.campaign_id, c.name, c.channel, c.start_time, c.end_time,
    c.budget, c.reward_type,
    coalesce(cu.participants, 0) as participants,
    coalesce(cu.new_users, 0) as new_users,
    coalesce(cu.reward_cost, 0) as reward_cost,
    coalesce(rev.revenue, 0) as revenue,
    case when (c.budget + coalesce(cu.reward_cost, 0)) > 0
         then coalesce(rev.revenue, 0) / (c.budget + cu.reward_cost) end as roi
from c
left join cu on c.campaign_id = cu.campaign_id
left join rev on c.campaign_id = rev.campaign_id
