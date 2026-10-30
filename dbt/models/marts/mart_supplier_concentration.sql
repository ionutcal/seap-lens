-- Market share of the top five suppliers by county, CPV group and year, on real contracts from 2023.
with supplier_totals as (
    select
        awards.contract_year as year,
        authorities.county,
        awards.cpv_group,
        awards.winner_cui as supplier_cui,
        sum(awards.value_ron) as value_ron
    from {{ ref('fct_awards') }} as awards
    left join {{ ref('dim_authority') }} as authorities on awards.authority_cui = authorities.authority_cui
    where awards.value_kind in ('subsequent_contract', 'standalone_contract')
        and awards.contract_year >= 2023
        and not awards.is_suspect_value
        and awards.winner_cui is not null
    group by 1, 2, 3, 4
),

ranked as (
    select
        *,
        row_number() over (partition by year, county, cpv_group order by value_ron desc) as supplier_rank,
        value_ron / sum(value_ron) over (partition by year, county, cpv_group) as market_share
    from supplier_totals
)

select * from ranked where supplier_rank <= 5
