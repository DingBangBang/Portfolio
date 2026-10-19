select tx_id
from {{ ref('stg_transactions') }}
where quote_amt <= 0 or fee < 0
