-- Real contracts only, by contract year from 2023. Joint winners repeat a contract's value, so each
-- contract counts once. The file year would be wrong: a contract can be republished years later.
with contracts as (
    select distinct
        contract_year as year,
        value_kind,
        award_notice_id,
        lot_number,
        contract_number,
        value_ron,
        is_suspect_value
    from {{ ref('fct_awards') }}
    where value_kind in ('subsequent_contract', 'standalone_contract')
        and contract_year >= 2023
)

select
    year,
    value_kind,
    count(*) as contracts,
    sum(case when is_suspect_value then 1 else 0 end) as suspect_contracts,
    sum(case when is_suspect_value then 0 else value_ron end) as contracted_value_ron,
    sum(case when is_suspect_value then value_ron else 0 end) as suspect_value_ron,
    {{ approx_median("case when is_suspect_value then null else value_ron end") }} as median_value_ron
from contracts
group by year, value_kind
