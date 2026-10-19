select 'cta' as experiment, 'cta_color=' || cta_color as variant,
       count(*) as n, sum(converted) as conversions, avg(converted) as cvr
from {{ ref('stg_cta') }} group by 1, 2
union all
select 'cta', 'cta_copy=' || cta_copy, count(*), sum(converted), avg(converted)
from {{ ref('stg_cta') }} group by 1, 2
union all
select 'cta', 'cta_size=' || cta_size, count(*), sum(converted), avg(converted)
from {{ ref('stg_cta') }} group by 1, 2
union all
select 'ab', variant, count(*), sum(converted), avg(converted)
from {{ ref('stg_ab') }} group by 1, 2
