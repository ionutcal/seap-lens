"""Exports the warehouse tables the dashboard reads into dashboard/data. Run from the repository root."""

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from src.warehouse import query

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "dashboard" / "data"
MODEL_DIR = ROOT / "data" / "model"
RESULTS_DIR = ROOT / "docs" / "model"
CALIBRATION_BINS = 10
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


def _single_value(sql: str):
    value = query(sql).iloc[0, 0]
    return value.item() if hasattr(value, "item") else value


def out_of_sample_predictions() -> pd.DataFrame:
    """Predictions for contracts each model had not seen: 2021 from validation, 2022 from the test."""
    selected = json.loads((RESULTS_DIR / "validation_result.json").read_text())["selected"]
    validation = pd.read_parquet(MODEL_DIR / "validation_predictions.parquet").rename(columns={selected: "prediction"})
    test = pd.read_parquet(MODEL_DIR / "test_predictions.parquet")
    columns = ["contract_key", "authority_cui", "period", "is_single_offer", "prediction"]
    return pd.concat([validation[columns], test[columns]], ignore_index=True)


def export_model_results() -> None:
    predictions = out_of_sample_predictions()
    (
        predictions.assign(single=predictions.is_single_offer.astype(int))
        .groupby(["authority_cui", "period"], as_index=False)
        .agg(contracts=("single", "size"), single_offer_contracts=("single", "sum"), expected_single_offers=("prediction", "sum"))
        .to_parquet(OUTPUT / "authority_expected.parquet", index=False)
    )
    test = pd.read_parquet(MODEL_DIR / "test_predictions.parquet")
    bins = pd.cut(test.prediction, [i / CALIBRATION_BINS for i in range(CALIBRATION_BINS + 1)], include_lowest=True)
    (
        test.assign(single=test.is_single_offer.astype(float), bin=bins.astype(str))
        .groupby("bin", as_index=False)
        .agg(contracts=("single", "size"), predicted=("prediction", "mean"), actual=("single", "mean"))
        .sort_values("predicted")
        .to_parquet(OUTPUT / "calibration.parquet", index=False)
    )
    (
        pd.read_parquet(MODEL_DIR / "notice_scores.parquet")
        .groupby(["authority_cui", "year"], as_index=False)
        .agg(notices=("estimated_risk", "size"), mean_risk=("estimated_risk", "mean"))
        .to_parquet(OUTPUT / "authority_risk.parquet", index=False)
    )
    summary = {name: json.loads((RESULTS_DIR / f"{name}_result.json").read_text()) for name in ("validation", "test", "drift")}
    (OUTPUT / "model_results.json").write_text(json.dumps(summary, indent=1) + "\n")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    export_model_results()
    for name, sql in QUERIES.items():
        query(sql).to_parquet(OUTPUT / f"{name}.parquet", index=False, compression="zstd")
    metadata = {name: _single_value(sql) for name, sql in COUNTS.items()}
    metadata["exported_on"] = dt.date.today().isoformat()
    (OUTPUT / "metadata.json").write_text(json.dumps(metadata, indent=1) + "\n")
    print(metadata)


if __name__ == "__main__":
    main()
