select t.tx_id
from {{ ref('stg_transactions') }} t
join {{ ref('stg_users') }} u on t.user_id = u.user_id
where t.tx_time < u.register_time
