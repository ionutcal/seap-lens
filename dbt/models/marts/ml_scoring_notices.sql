-- Procedures published after bid counts stopped, for scores that can't be validated.
select
    procedures.notice_id,
    procedures.notice_date as publication_date,
    procedures.authority_cui,
    procedures.cpv_group,
    procedures.contract_type,
    procedures.procedure_type,
    procedures.estimated_value_ron,
    authorities.authority_type
from {{ ref('fct_procedures') }} as procedures
left join {{ ref('dim_authority') }} as authorities on procedures.authority_cui = authorities.authority_cui
where year(procedures.notice_date) >= 2023
    and coalesce(procedures.procedure_type, '') not in ('Negociere fara anunt de participare', 'Negociere', 'Negociere accelerata')
