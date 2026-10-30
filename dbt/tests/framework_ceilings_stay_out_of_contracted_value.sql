select year, value_kind
from {{ ref('mart_contracted_value') }}
where value_kind = 'framework_ceiling' or year < 2023
