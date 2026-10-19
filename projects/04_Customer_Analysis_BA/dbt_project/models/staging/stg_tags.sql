select
    user_id,
    tag,
    tag_type,
    cast(weight as double) as weight
from {{ source('raw', 'dim_user_tags') }}
