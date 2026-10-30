select contract_key
from {{ ref('fct_contract_competition') }}
where is_single_offer != (bid_count = 1)
    or (bid_count is null and is_single_offer is not null)
