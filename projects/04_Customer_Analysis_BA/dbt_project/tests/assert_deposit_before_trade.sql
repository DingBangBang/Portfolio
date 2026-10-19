select user_id
from {{ ref('mart_user_360') }}
where first_trade_time is not null
  and (first_deposit_time is null or first_trade_time < first_deposit_time)
