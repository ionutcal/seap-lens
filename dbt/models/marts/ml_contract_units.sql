-- One row per labelled contract, with only what was known when its notice was published,
-- plus the award date and label the training code needs to build history and split time.
with contracts as (
    select
        award_notice_id,
        contract_number,
        min(participation_notice_date) as publication_date,
        any_value(case when estimated_currency = 'RON' then estimated_value end) as estimated_value_ron
    from {{ ref('stg_contracts') }}
    where contract_number is not null
    group by award_notice_id, contract_number
)

select
    competition.contract_key,
    competition.award_notice_id,
    competition.contract_number,
    competition.participation_notice_id,
    competition.authority_cui,
    competition.award_notice_date,
    competition.first_file_order,
    competition.is_single_offer,
    competition.cpv_group,
    competition.contract_type,
    competition.procedure_type,
    authorities.authority_type,
    contracts.publication_date,
    contracts.estimated_value_ron
from {{ ref('fct_contract_competition') }} as competition
inner join contracts using (award_notice_id, contract_number)
left join {{ ref('dim_authority') }} as authorities on competition.authority_cui = authorities.authority_cui
where competition.bid_count is not null
    and not competition.is_without_real_competition
