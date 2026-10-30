with from_contracts as (
    select
        authority_cui,
        arg_max(authority_name, file_order) as authority_name,
        arg_max(authority_type, file_order) filter (where authority_type is not null) as authority_type,
        arg_max(authority_activity, file_order) filter (where authority_activity is not null) as authority_activity
    from {{ ref('stg_contracts') }}
    where authority_cui is not null
    group by authority_cui
),

from_notices as (
    select
        authority_cui,
        arg_max(authority_name, file_order) as authority_name,
        arg_max(county, file_order) filter (where county is not null) as county
    from {{ ref('stg_notices') }}
    where authority_cui is not null
    group by authority_cui
)

select
    coalesce(c.authority_cui, n.authority_cui) as authority_cui,
    coalesce(c.authority_name, n.authority_name) as authority_name,
    c.authority_type,
    c.authority_activity,
    n.county
from from_contracts as c
full outer join from_notices as n on c.authority_cui = n.authority_cui
