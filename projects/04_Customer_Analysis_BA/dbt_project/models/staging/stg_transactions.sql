select
    tx_id,
    user_id,
    cast(tx_time as timestamp) as tx_time,
    record_type,
    symbol,
    cast(quote_amt as double) as quote_amt,
    cast(is_otc as boolean) as is_otc,
    cast(fee as double) as fee
from {{ source('raw', 'fact_transactions') }}
