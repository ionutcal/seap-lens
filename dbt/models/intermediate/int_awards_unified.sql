-- A contract republished in a later file can change value, so only its latest file counts.
-- Rows in that file can still differ by value: older files have no lots, so one contract
-- number can cover several real items.
with ranked as (
    select
        *,
        max(file_order) over (partition by award_notice_id, lot_number, contract_number, winner_cui) as latest_file_order,
        min(file_order) over (partition by award_notice_id, lot_number, contract_number, winner_cui) as first_file_order
    from {{ ref('stg_contracts') }}
),

latest as (
    select
        *,
        row_number() over (
            partition by award_notice_id, lot_number, contract_number, winner_cui, value_ron
            order by award_notice_date desc
        ) as value_rank
    from ranked
    where file_order = latest_file_order
)

select * exclude (value_rank, latest_file_order), latest_file_order
from latest
where value_rank = 1
