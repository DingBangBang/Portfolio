select
    exp_id,
    user_id,
    cta_color,
    cta_copy,
    cta_size,
    cast(impression as integer) as impression,
    cast(clicked as integer) as clicked,
    cast(converted as integer) as converted
from {{ source('raw', 'fact_cta_experiments') }}
