select
    winner_cui as supplier_cui,
    arg_max(winner_name, file_order) as supplier_name,
    arg_max(winner_country, file_order) filter (where winner_country is not null) as country
from {{ ref('stg_contracts') }}
where winner_cui is not null
group by winner_cui
