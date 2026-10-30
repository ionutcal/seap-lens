select
    award_notice_id,
    award_notice_date,
    nullif(trim(participation_notice_id), '') as participation_notice_id,
    participation_notice_date,
    nullif(trim(lot_number), '') as lot_number,
    nullif(trim(contract_number), '') as contract_number,
    contract_date,
    trim(contract_title) as contract_title,
    trim(contract_type) as contract_type,
    trim(procedure_type) as procedure_type,
    trim(agreement_type) as agreement_type,
    trim(concluded_through) as concluded_through,
    authority_cui,
    trim(authority_name) as authority_name,
    trim(authority_type) as authority_type,
    trim(authority_activity) as authority_activity,
    winner_cui,
    trim(winner_name) as winner_name,
    trim(winner_country) as winner_country,
    trim(cpv_code) as cpv_code,
    trim(cpv_name) as cpv_name,
    substr(trim(cpv_code), 1, 2) as cpv_group,
    cast(value_ron as double) as value_ron,
    cast(bid_count as double) as bid_count,
    cast(estimated_value as double) as estimated_value,
    trim(estimated_currency) as estimated_currency,
    file_year,
    file_period,
    file_year * 10 + case file_period
        when 'Q1' then 1 when 'Q2' then 2 when 'Q3' then 3 when 'Q4' then 4
        when 'S1' then 2 when 'S2' then 4 else 4
    end as file_order
from {{ source('standard', 'contracts') }}
