-- Reconciliation: a removed republication must still be represented by its latest version.
select source.award_notice_id, source.contract_number
from {{ ref('stg_contracts') }} as source
left join {{ ref('fct_awards') }} as awards
    on source.award_notice_id = awards.award_notice_id
    and source.lot_number is not distinct from awards.lot_number
    and source.contract_number is not distinct from awards.contract_number
    and source.winner_cui is not distinct from awards.winner_cui
where awards.award_notice_id is null
