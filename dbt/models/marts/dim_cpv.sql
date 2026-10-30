with codes as (
    select cpv_code, cpv_name, file_order from {{ ref('stg_contracts') }} where cpv_code is not null
    union all
    select cpv_code, cpv_name, file_order from {{ ref('stg_notices') }} where cpv_code is not null
)

select
    cpv_code,
    left(cpv_code, 2) as cpv_group,
    arg_max(cpv_name, file_order) filter (where cpv_name is not null) as cpv_name
from codes
group by cpv_code
