"""Prints the headline figures of the built warehouse. Run from the repository root."""

import os

import duckdb

QUERIES = {
    "rows": """
        select (select count(*) from stg_contracts) as source_contract_rows,
               (select count(*) from fct_awards) as awards,
               (select count(*) from fct_contract_competition) as contracts,
               (select count(*) from fct_procedures) as procedures,
               (select count(*) from dim_authority) as authorities,
               (select count(*) from dim_supplier) as suppliers
    """,
    "republished rows by file year": """
        with ranked as (
            select file_year, row_number() over (
                partition by award_notice_id, lot_number, contract_number, winner_cui order by file_order
            ) as appearance
            from stg_contracts
        )
        select file_year, count(*) as source_rows,
               round(avg(case when appearance > 1 then 1.0 else 0 end), 3) as already_seen_share
        from ranked group by 1 order by 1
    """,
    "republished keys whose value changed": """
        with keys as (
            select count(distinct file_order) as files, count(distinct value_ron) as values_seen
            from stg_contracts group by award_notice_id, lot_number, contract_number, winner_cui
        )
        select count(*) as keys, sum(case when files > 1 then 1 else 0 end) as republished,
               sum(case when files > 1 and values_seen > 1 then 1 else 0 end) as value_changed
        from keys
    """,
    "labels by first appearance": """
        select first_file_order // 10 as year,
               sum(case when bid_count is not null then 1 else 0 end) as labelled,
               sum(case when bid_count is not null and not is_without_real_competition then 1 else 0 end) as usable,
               round(avg(case when bid_count is not null and not is_without_real_competition
                              then case when is_single_offer then 1.0 else 0 end end), 3) as single_offer_share
        from fct_contract_competition group by 1 order by 1
    """,
    "contracted value": "select * from mart_contracted_value order by 1, 2",
    "value kinds": """
        select value_kind, count(*) as awards,
               round(avg(case when value_ron is null then 1.0 else 0 end), 4) as null_share,
               median(value_ron) as median_ron,
               sum(case when is_suspect_value then 1 else 0 end) as suspect
        from fct_awards group by 1 order by 1
    """,
    "largest values that are not ceilings": """
        select distinct round(value_ron / 1e9, 2) as value_bn, round(estimated_value_ron / 1e9, 4) as estimate_bn,
               value_kind, is_suspect_value, award_notice_id
        from fct_awards where value_kind != 'framework_ceiling'
        order by 1 desc nulls last limit 6
    """,
    "ceilings": """
        select contract_year, count(*) as awards, round(sum(value_ron) / 1e9, 1) as sum_bn, round(max(value_ron) / 1e9, 1) as max_bn
        from fct_awards where value_kind = 'framework_ceiling' and contract_year >= 2023 group by 1 order by 1
    """,
    "county coverage": """
        select round(avg(case when d.county is null then 1.0 else 0 end), 4) as awards_without_county
        from fct_awards a left join dim_authority d using (authority_cui)
    """,
}


def main() -> None:
    # Staging views read Parquet through paths relative to the dbt folder.
    os.chdir("dbt")
    connection = duckdb.connect("../data/warehouse.duckdb", read_only=True)
    for title, query in QUERIES.items():
        print(f"\n== {title}")
        print(connection.execute(query).df().to_string(index=False))


if __name__ == "__main__":
    main()
