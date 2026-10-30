-- Only years with bid counts appear, and only procedures where competition was possible.
select
    competition.authority_cui,
    year(competition.award_notice_date) as year,
    count(*) as contracts,
    sum(case when competition.is_single_offer then 1 else 0 end) as single_offer_contracts,
    avg(case when competition.is_single_offer then 1.0 else 0.0 end) as single_offer_share
from {{ ref('fct_contract_competition') }} as competition
where competition.bid_count is not null
    and not competition.is_without_real_competition
group by competition.authority_cui, year(competition.award_notice_date)
