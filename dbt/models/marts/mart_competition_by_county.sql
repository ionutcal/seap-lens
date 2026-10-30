-- Only years with bid counts appear, and only procedures where competition was possible.
select
    authorities.county,
    year(competition.award_notice_date) as year,
    count(*) as contracts,
    sum(case when competition.is_single_offer then 1 else 0 end) as single_offer_contracts
from {{ ref('fct_contract_competition') }} as competition
left join {{ ref('dim_authority') }} as authorities on competition.authority_cui = authorities.authority_cui
where competition.bid_count is not null
    and not competition.is_without_real_competition
group by authorities.county, year(competition.award_notice_date)
