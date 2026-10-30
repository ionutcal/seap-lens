-- The source stopped publishing bid counts. Any value here means a column was mapped wrongly.
select award_notice_id
from {{ ref('stg_contracts') }}
where file_year >= 2023 and bid_count is not null
