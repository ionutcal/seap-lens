select
    notice_id,
    notice_date,
    trim(notice_type) as notice_type,
    authority_cui,
    trim(authority_name) as authority_name,
    trim(county) as county,
    trim(contract_type) as contract_type,
    trim(procedure_type) as procedure_type,
    trim(procedure_status) as procedure_status,
    trim(cpv_code) as cpv_code,
    trim(cpv_name) as cpv_name,
    substr(trim(cpv_code), 1, 2) as cpv_group,
    trim(procedure_title) as procedure_title,
    cast(estimated_value as double) as estimated_value,
    trim(estimated_currency) as estimated_currency,
    file_year,
    file_period,
    file_year * 10 + case file_period
        when 'Q1' then 1 when 'Q2' then 2 when 'Q3' then 3 when 'Q4' then 4
        when 'S1' then 2 when 'S2' then 4 else 4
    end as file_order
from {{ source('standard', 'notices') }}
