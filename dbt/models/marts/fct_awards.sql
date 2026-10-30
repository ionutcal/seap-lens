with awards as (
    select * from {{ ref('int_awards_unified') }}
),

classified as (
    select
        awards.*,
        procedures.estimated_value_ron,
        case
            when awards.concluded_through = 'Cu acord cadru' then 'framework_ceiling'
            when awards.concluded_through = 'Cu acord cadru subsecvent' then 'subsequent_contract'
            when awards.concluded_through = 'Fara acord cadru' then 'standalone_contract'
            else 'not_published'
        end as value_kind
    from awards
    left join {{ ref('fct_procedures') }} as procedures
        on awards.participation_notice_id = procedures.notice_id
)

select
    {{ row_key(["award_notice_id", "coalesce(lot_number, '')", "coalesce(contract_number, '')",
                "coalesce(winner_cui, '')", "coalesce(cast(value_ron as varchar), '')"]) }} as award_key,
    award_notice_id,
    award_notice_date,
    participation_notice_id,
    lot_number,
    contract_number,
    contract_date,
    year(contract_date) as contract_year,
    contract_type,
    procedure_type,
    authority_cui,
    winner_cui,
    cpv_code,
    cpv_group,
    value_ron,
    value_kind,
    estimated_value_ron,
    coalesce(
        value_ron <= 0
        or value_ron > {{ var('suspect_value_ron') }}
        or value_ron > {{ var('suspect_estimate_multiple') }} * estimated_value_ron,
        false
    ) as is_suspect_value,
    file_year,
    first_file_order,
    latest_file_order
from classified
