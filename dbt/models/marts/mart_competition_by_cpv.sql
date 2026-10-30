-- Only years with bid counts appear, and only procedures where competition was possible.
select
    competition.cpv_group,
    year(competition.award_notice_date) as year,
    count(*) as contracts,
    sum(case when competition.is_single_offer then 1 else 0 end) as single_offer_contracts
from {{ ref('fct_contract_competition') }} as competition
where competition.bid_count is not null
    and not competition.is_without_real_competition
    and competition.cpv_group is not null
group by competition.cpv_group, year(competition.award_notice_date)
