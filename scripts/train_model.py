"""Trains, tests and applies the single-offer model.

    python -m scripts.train_model validate    choose the variant on 2021
    python -m scripts.train_model test        run the 2022 test, which works only once
    python -m scripts.train_model score       score notices from 2023, and measure drift
"""

import json
import sys
from pathlib import Path

import duckdb
import joblib
import mlflow
import pandas as pd
from sklearn.metrics import average_precision_score

from src.model_evaluation import (
    PSI_WARNING, categorical_psi, clustered_pr_auc_interval, evaluate, numeric_psi, select_variant,
)
from src.model_features import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, assign_periods, build_features
from src.model_variants import SEARCH_SPACE, VARIANT_ORDER, VARIANTS

WAREHOUSE = "data/warehouse.duckdb"
MODEL_DIR = Path("data/model")
RESULTS_DIR = Path("docs/model")
VALIDATION_RESULT = RESULTS_DIR / "validation_result.json"
TEST_RESULT = RESULTS_DIR / "test_result.json"
DRIFT_RESULT = RESULTS_DIR / "drift_result.json"
TEST_PERIOD = 2022
VALIDATION_PERIOD = 2021
TUNING_PERIOD = 2020


def load_units() -> pd.DataFrame:
    connection = duckdb.connect(WAREHOUSE, read_only=True)
    units = connection.execute("select * from ml_contract_units").df()
    events = units[["authority_cui", "award_notice_date", "is_single_offer"]]
    excluded = int(units.publication_date.isna().sum())
    units = units[units.publication_date.notna()].reset_index(drop=True)
    features = build_features(units, events)
    features.attrs["excluded_without_publication_date"] = excluded
    features["period"] = assign_periods(features)
    features["procedure"] = features.participation_notice_id.where(features.participation_notice_id.notna(), features.award_notice_id)
    return features


def fit(variant: str, parameters: dict, frame: pd.DataFrame):
    return VARIANTS[variant](**parameters).fit(frame, frame.is_single_offer)


def tune(variant: str, units: pd.DataFrame) -> dict:
    """Pick parameters on 2020, fitting on the years before it."""
    train, tuning = units[units.period < TUNING_PERIOD], units[units.period == TUNING_PERIOD]
    scores = [
        (average_precision_score(tuning.is_single_offer.astype(int), fit(variant, parameters, train).predict(tuning)), index)
        for index, parameters in enumerate(SEARCH_SPACE[variant])
    ]
    return SEARCH_SPACE[variant][max(scores)[1]]


def validate() -> None:
    units = load_units()
    train, validation = units[units.period < VALIDATION_PERIOD], units[units.period == VALIDATION_PERIOD]
    results, predictions = {}, validation[["contract_key", "authority_cui", "period", "is_single_offer"]].copy()
    for variant in VARIANT_ORDER:
        parameters = tune(variant, units)
        model = fit(variant, parameters, train)
        predicted = model.predict(validation)
        predictions[variant] = predicted
        results[variant] = {"parameters": parameters, **evaluate(validation.is_single_offer, predicted, validation.procedure)}
        with mlflow.start_run(run_name=f"validate-{variant}"):
            mlflow.log_params({"variant": variant, **parameters})
            mlflow.log_metrics({key: value for key, value in results[variant].items() if isinstance(value, float)})
    selected = select_variant(results, VARIANT_ORDER)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(MODEL_DIR / "validation_predictions.parquet", index=False)
    result = {
        "selected": selected, "train_rows": len(train), "train_periods": sorted(int(p) for p in train.period.unique()),
        "excluded_without_publication_date": units.attrs["excluded_without_publication_date"], "variants": results,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_RESULT.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))


def test() -> None:
    if TEST_RESULT.exists():
        sys.exit(f"The test already ran, and it runs only once: see {TEST_RESULT}")
    validation_result = json.loads(VALIDATION_RESULT.read_text())
    selected = validation_result["selected"]
    parameters = validation_result["variants"][selected]["parameters"]
    units = load_units()
    train, held_out = units[units.period < TEST_PERIOD], units[units.period == TEST_PERIOD]
    # The baseline travels with the test, so the published result always shows the comparison.
    baseline = fit("mean_rate", {}, train).predict(held_out)
    model = fit(selected, parameters, train)
    predicted = model.predict(held_out)
    low, high = clustered_pr_auc_interval(held_out.is_single_offer, predicted, held_out.procedure)
    result = {
        "selected": selected, "parameters": parameters, "train_rows": len(train),
        "model": {**evaluate(held_out.is_single_offer, predicted, held_out.procedure), "pr_auc_low": low, "pr_auc_high": high},
        "baseline": evaluate(held_out.is_single_offer, baseline, held_out.procedure),
    }
    with mlflow.start_run(run_name=f"test-{selected}"):
        mlflow.log_params({"variant": selected, **parameters})
        mlflow.log_metrics({key: value for key, value in result["model"].items() if isinstance(value, float)})
    TEST_RESULT.write_text(json.dumps(result, indent=1) + "\n")
    held_out.assign(prediction=predicted)[["contract_key", "authority_cui", "period", "is_single_offer", "prediction"]].to_parquet(
        MODEL_DIR / "test_predictions.parquet", index=False
    )
    joblib.dump(model, MODEL_DIR / "final_model.joblib")
    print(json.dumps(result, indent=1))


def drift_against(train: pd.DataFrame, group: pd.DataFrame) -> dict:
    values = {feature: numeric_psi(train[feature], group[feature]) for feature in NUMERIC_FEATURES}
    values.update({feature: categorical_psi(train[feature], group[feature]) for feature in CATEGORICAL_FEATURES})
    return {
        "procedures": len(group),
        "psi": {feature: round(values[feature], 4) for feature in FEATURES},
        # A partial year always looks different by month, which says nothing about drift.
        "above_warning": sorted(f for f in FEATURES if values[f] > PSI_WARNING and f != "publication_month"),
    }


def score() -> None:
    model = joblib.load(MODEL_DIR / "final_model.joblib")
    units = load_units()
    train = units[units.period < TEST_PERIOD]
    notices = duckdb.connect(WAREHOUSE, read_only=True).execute("select * from ml_scoring_notices").df()
    notices = notices[notices.publication_date.notna()].reset_index(drop=True)
    events = units[["authority_cui", "award_notice_date", "is_single_offer"]]
    scored = build_features(notices, events)
    scored["estimated_risk"] = model.predict(scored)
    scored["year"] = scored.publication_date.dt.year
    scored[["notice_id", "authority_cui", "year", "estimated_risk"]].to_parquet(MODEL_DIR / "notice_scores.parquet", index=False)
    # Notices are procedures, so training data must be compared per procedure too. Per contract,
    # a few frameworks with thousands of contracts would dominate and look like drift.
    train_procedures = train.drop_duplicates("procedure")
    reference = units[units.period == TEST_PERIOD].drop_duplicates("procedure")
    drift = {"reference_2022": drift_against(train_procedures, reference)}
    for year, group in scored.groupby("year"):
        drift[int(year)] = {**drift_against(train_procedures, group), "mean_risk": float(group.estimated_risk.mean())}
    DRIFT_RESULT.write_text(json.dumps(drift, indent=1) + "\n")
    print(json.dumps(drift, indent=1))


def main() -> None:
    mlflow.set_tracking_uri("sqlite:///data/mlflow.db")
    mlflow.set_experiment("seap-lens")
    {"validate": validate, "test": test, "score": score}[sys.argv[1]]()


if __name__ == "__main__":
    main()
