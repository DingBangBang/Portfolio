with agg as (
    select page, module_id,
           sum(impressions) as impressions,
           sum(clicks) as clicks,
           avg(module_area_pct) as area_pct
    from {{ ref('stg_page_modules') }}
    group by 1, 2
),
tot as (
    select page, sum(impressions) as page_impressions, sum(clicks) as page_clicks
    from agg group by 1
)
select
    a.page, a.module_id, a.impressions, a.clicks, a.area_pct,
    a.clicks * 1.0 / nullif(t.page_clicks, 0) as click_share,
    a.impressions * 1.0 / nullif(t.page_impressions, 0) as impression_share,
    (a.clicks * 1.0 / nullif(t.page_clicks, 0)) /
    nullif(a.impressions * 1.0 / nullif(t.page_impressions, 0), 0) as relative_clickability,
    a.clicks * 1.0 / nullif(a.impressions, 0) as ctr
from agg a
join tot t on a.page = t.page
