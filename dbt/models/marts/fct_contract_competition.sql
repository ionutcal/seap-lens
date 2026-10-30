-- The bid count belongs to the contract within an award notice. Where rows disagree the maximum
-- applies, so a contract is single-offer only if every row says so.
select
    {{ row_key(["award_notice_id", "contract_number"]) }} as contract_key,
    award_notice_id,
    contract_number,
    {{ pick_any("participation_notice_id") }} as participation_notice_id,
    min(award_notice_date) as award_notice_date,
    {{ pick_any("authority_cui") }} as authority_cui,
    {{ pick_any("procedure_type") }} as procedure_type,
    {{ pick_any("contract_type") }} as contract_type,
    {{ pick_any("cpv_group") }} as cpv_group,
    max(bid_count) as bid_count,
    max(bid_count) = 1 as is_single_offer,
    {{ pick_any("procedure_type") }} in ('Negociere fara anunt de participare', 'Negociere', 'Negociere accelerata')
        as is_without_real_competition,
    min(file_order) as first_file_order
from {{ ref('stg_contracts') }}
where contract_number is not null
group by award_notice_id, contract_number
