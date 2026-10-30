import numpy as np
import pandas as pd
import pytest

from src.model_evaluation import (
    categorical_psi, expected_calibration_error, improves_on, numeric_psi, select_variant,
)
from src.model_features import FEATURES, add_authority_history, assign_periods, build_features
from src.model_variants import LightGBMModel, LogisticModel, MeanRateModel


def events(*rows):
    return pd.DataFrame(rows, columns=["authority_cui", "award_notice_date", "is_single_offer"]).assign(
        award_notice_date=lambda f: pd.to_datetime(f.award_notice_date)
    )


def rows(*items):
    return pd.DataFrame(items, columns=["authority_cui", "publication_date"]).assign(
        publication_date=lambda f: pd.to_datetime(f.publication_date)
    )


def test_history_uses_only_awards_before_publication():
    history = add_authority_history(
        rows(("A", "2020-06-01")),
        events(("A", "2020-01-01", True), ("A", "2020-06-01", True), ("A", "2020-07-01", True)),
    )
    # The award on the same day and the later one can't be known yet.
    assert history.history_contracts.tolist() == [1]
    assert history.history_single.tolist() == [1]


def test_history_is_kept_apart_per_authority_and_keeps_row_order():
    history = add_authority_history(
        rows(("B", "2021-01-01"), ("A", "2020-01-01"), ("C", "2021-01-01")),
        events(("A", "2019-01-01", False), ("B", "2019-01-01", True), ("B", "2020-01-01", False)),
    )
    assert history.authority_cui.tolist() == ["B", "A", "C"]
    assert history.history_contracts.tolist() == [2, 1, 0]
    assert history.history_single.tolist() == [1, 0, 0]


def unit(**overrides):
    base = {
        "authority_cui": "A", "publication_date": pd.Timestamp("2021-03-01"), "estimated_value_ron": 1000.0,
        "cpv_group": "33", "contract_type": "Furnizare", "procedure_type": "Licitatie deschisa", "authority_type": None,
    }
    return {**base, **overrides}


def test_features_never_include_anything_known_only_after_award():
    forbidden = {"is_single_offer", "bid_count", "value_ron", "winner_cui", "contract_date", "award_notice_date", "contract_number"}
    assert not forbidden & set(FEATURES)


def test_build_features_handles_missing_values_and_short_history():
    built = build_features(pd.DataFrame([unit(estimated_value_ron=None)]), events(("A", "2020-01-01", True)))
    row = built.iloc[0]
    assert np.isnan(row.log_estimated_value)
    assert row.authority_type == "unknown"
    assert row.publication_month == 3
    assert np.isnan(row.history_single_share)


def test_contracts_of_one_procedure_stay_in_the_period_it_first_appeared():
    frame = pd.DataFrame({
        "first_file_order": [20211, 20223, 20223, 20224],
        "participation_notice_id": ["CN1", "CN1", "CN2", None],
        "award_notice_id": ["CAN1", "CAN2", "CAN3", "CAN4"],
    })
    assert assign_periods(frame).tolist() == [2021, 2021, 2022, 2022]


def test_calibration_error_is_zero_when_predictions_match_the_rates():
    assert expected_calibration_error([1, 0, 0, 0], [0.25] * 4) == pytest.approx(0)
    assert expected_calibration_error([1, 1, 1, 1], [0.25] * 4) == pytest.approx(0.75)


@pytest.mark.parametrize(
    "gain,calibration_change,expected",
    [(0.02, 0.0, True), (0.019, 0.0, False), (0.05, 0.005, True), (0.05, 0.02, False)],
)
def test_a_model_must_earn_its_complexity(gain, calibration_change, expected):
    current = {"pr_auc": 0.5, "calibration_error": 0.01}
    candidate = {"pr_auc": 0.5 + gain, "calibration_error": 0.01 + calibration_change}
    assert improves_on(candidate, current) is expected


def test_selection_keeps_the_simplest_variant_that_is_not_beaten():
    results = {
        "mean_rate": {"pr_auc": 0.40, "calibration_error": 0.01},
        "logistic": {"pr_auc": 0.45, "calibration_error": 0.01},
        "lightgbm": {"pr_auc": 0.46, "calibration_error": 0.01},
    }
    assert select_variant(results, ["mean_rate", "logistic", "lightgbm"]) == "logistic"


def test_psi_is_near_zero_for_the_same_data_and_large_after_a_shift():
    generator = np.random.default_rng(0)
    base = pd.Series(generator.normal(0, 1, 5000))
    assert numeric_psi(base, pd.Series(generator.normal(0, 1, 5000))) < 0.02
    assert numeric_psi(base, pd.Series(generator.normal(3, 1, 5000))) > 0.25
    assert categorical_psi(pd.Series(["a"] * 90 + ["b"] * 10), pd.Series(["a"] * 10 + ["b"] * 90)) > 0.25


def test_missing_values_count_as_their_own_group_in_psi():
    base = pd.Series(np.arange(1000, dtype=float))
    assert numeric_psi(base, pd.Series([np.nan] * 1000)) > 0.25


def training_frame():
    size = 400
    frame = pd.DataFrame({
        "cpv_group": ["33", "45"] * (size // 2), "contract_type": "Furnizare", "procedure_type": "Licitatie deschisa",
        "authority_type": "Comuna", "log_estimated_value": 1.0, "publication_month": 1.0,
        "log_history_contracts": 1.0, "history_single_share": [0.1, np.nan] * (size // 2),
    })
    return frame, pd.Series([True, False] * (size // 2))


@pytest.mark.parametrize("model", [MeanRateModel(), LogisticModel(), LightGBMModel(min_child_samples=5)])
def test_every_variant_learns_a_clear_signal_and_accepts_unseen_categories(model):
    frame, labels = training_frame()
    model.fit(frame, labels)
    predicted = model.predict(frame)
    assert predicted[0] > 0.8 and predicted[1] < 0.2
    unseen = frame.head(1).assign(cpv_group="99", procedure_type="new")
    assert 0 <= model.predict(unseen)[0] <= 1
