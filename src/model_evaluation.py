"""Measures predictions and applies the spec's rule for choosing a model."""

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss

MIN_PR_AUC_GAIN = 0.02
# Calibration differences below this are noise, so they don't count as worse.
CALIBRATION_TOLERANCE = 0.005
PSI_WARNING = 0.25


def expected_calibration_error(labels, predictions, bins: int = 10) -> float:
    """Average gap between predicted and actual rates, across equal-width probability bins."""
    labels, predictions = np.asarray(labels, dtype=float), np.asarray(predictions, dtype=float)
    edges = np.minimum((predictions * bins).astype(int), bins - 1)
    error = 0.0
    for current in np.unique(edges):
        members = edges == current
        error += members.mean() * abs(labels[members].mean() - predictions[members].mean())
    return float(error)


def evaluate(labels, predictions, procedures=None) -> dict:
    labels = np.asarray(labels, dtype=int)
    metrics = {
        "rows": int(len(labels)),
        "base_rate": float(labels.mean()),
        "pr_auc": float(average_precision_score(labels, predictions)),
        "calibration_error": expected_calibration_error(labels, predictions),
        "brier": float(brier_score_loss(labels, predictions)),
    }
    if procedures is not None:
        # A framework with thousands of contracts would otherwise dominate the score.
        counts = pd.Series(procedures).map(pd.Series(procedures).value_counts()).to_numpy()
        metrics["pr_auc_per_procedure"] = float(average_precision_score(labels, predictions, sample_weight=1 / counts))
        metrics["procedures"] = int(pd.Series(procedures).nunique())
    return metrics


def clustered_pr_auc_interval(labels, predictions, procedures, resamples: int = 200, seed: int = 0) -> tuple[float, float]:
    """95% bootstrap interval that resamples whole procedures, because their contracts move together."""
    frame = pd.DataFrame({"label": np.asarray(labels, dtype=int), "prediction": np.asarray(predictions), "procedure": np.asarray(procedures)})
    groups = [group for _, group in frame.groupby("procedure")]
    generator = np.random.default_rng(seed)
    scores = []
    for _ in range(resamples):
        chosen = generator.integers(0, len(groups), len(groups))
        sample = pd.concat([groups[i] for i in chosen], ignore_index=True)
        scores.append(average_precision_score(sample.label, sample.prediction))
    return float(np.quantile(scores, 0.025)), float(np.quantile(scores, 0.975))


def improves_on(candidate: dict, current: dict) -> bool:
    """The spec's rule: PR-AUC at least 0.02 higher, and calibration no worse."""
    return (
        candidate["pr_auc"] >= current["pr_auc"] + MIN_PR_AUC_GAIN
        and candidate["calibration_error"] <= current["calibration_error"] + CALIBRATION_TOLERANCE
    )


def select_variant(results: dict[str, dict], order: list[str]) -> str:
    """Start from the simplest variant and move up only when the next one earns it."""
    selected = order[0]
    for candidate in order[1:]:
        if improves_on(results[candidate], results[selected]):
            selected = candidate
    return selected


def numeric_psi(expected: pd.Series, actual: pd.Series, bins: int = 10) -> float:
    edges = np.unique(np.nanquantile(expected.dropna().to_numpy(dtype=float), np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    return _psi(
        pd.cut(expected, edges).astype("object").where(expected.notna(), "missing"),
        pd.cut(actual, edges).astype("object").where(actual.notna(), "missing"),
    )


def categorical_psi(expected: pd.Series, actual: pd.Series) -> float:
    return _psi(expected.astype("object"), actual.astype("object"))


def _psi(expected: pd.Series, actual: pd.Series) -> float:
    categories = sorted(set(map(str, expected.unique())) | set(map(str, actual.unique())))
    floor = 1e-4
    expected_share = expected.astype(str).value_counts(normalize=True).reindex(categories, fill_value=0).clip(lower=floor)
    actual_share = actual.astype(str).value_counts(normalize=True).reindex(categories, fill_value=0).clip(lower=floor)
    return float(((actual_share - expected_share) * np.log(actual_share / expected_share)).sum())
