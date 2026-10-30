"""Exports the warehouse tables the dashboard reads into dashboard/data. Run from the repository root."""

import datetime as dt
import json
import os
from pathlib import Path

import duckdb

OUTPUT = Path(__file__).resolve().parent.parent / "dashboard" / "data"
QUERIES = {
    "competition_by_county": "select * from mart_competition_by_county where year >= 2016",
    "competition_by_cpv": """
        select competition.*, regexp_replace(groups.cpv_name, ' \\(Rev\\.2\\)$', '') as cpv_group_name
        from mart_competition_by_cpv as competition
        left join dim_cpv as groups
            on groups.cpv_group = competition.cpv_group and groups.cpv_code like '__000000-%'
        where competition.year >= 2016
    """,
    "competition_by_authority": """
        select competition.authority_cui, authorities.authority_name, authorities.county,
               competition.year, competition.contracts, competition.single_offer_contracts
        from mart_authority_competition as competition
        left join dim_authority as authorities using (authority_cui)
        where competition.year >= 2016
    """,
    "contracted_value": "select * from mart_contracted_value where year <= year(current_date)",
    "supplier_concentration": """
        select concentration.year, concentration.county, concentration.cpv_group,
               regexp_replace(groups.cpv_name, ' \\(Rev\\.2\\)$', '') as cpv_group_name,
               suppliers.supplier_name, concentration.supplier_rank,
               concentration.value_ron, concentration.market_share
        from mart_supplier_concentration as concentration
        left join dim_supplier as suppliers using (supplier_cui)
        left join dim_cpv as groups
            on groups.cpv_group = concentration.cpv_group and groups.cpv_code like '__000000-%'
        where concentration.county is not null
    """,
}
COUNTS = {
    "awards": "select count(*) from fct_awards",
    "contracts_with_bid_count": """
        select count(*) from fct_contract_competition
        where bid_count is not null and not is_without_real_competition
    """,
    "last_award_date": "select cast(max(award_notice_date) as varchar) from fct_awards",
    "suspect_contracts": "select cast(sum(suspect_contracts) as bigint) from mart_contracted_value",
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Staging views read Parquet through paths relative to the dbt folder.
    os.chdir("dbt")
    connection = duckdb.connect("../data/warehouse.duckdb", read_only=True)
    for name, query in QUERIES.items():
        connection.execute(f"copy ({query}) to '{OUTPUT / name}.parquet' (format parquet, compression zstd)")
    metadata = {name: connection.execute(query).fetchone()[0] for name, query in COUNTS.items()}
    metadata["exported_on"] = dt.date.today().isoformat()
    (OUTPUT / "metadata.json").write_text(json.dumps(metadata, indent=1) + "\n")
    print(metadata)


if __name__ == "__main__":
    main()
