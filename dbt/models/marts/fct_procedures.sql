-- From 2026 Q3 notices have one row per lot, so the latest row of each notice stands for the procedure.
with ranked as (
    select
        *,
        row_number() over (partition by notice_id order by file_order desc, notice_date desc) as notice_rank
    from {{ ref('stg_notices') }}
)

select
    notice_id,
    notice_date,
    authority_cui,
    contract_type,
    procedure_type,
    cpv_code,
    cpv_group,
    procedure_title,
    case when estimated_currency = 'RON' then estimated_value end as estimated_value_ron,
    file_order
from ranked
where notice_rank = 1
