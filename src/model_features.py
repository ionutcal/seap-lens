"""Builds model features from what is known when a notice is published."""

import numpy as np
import pandas as pd

CATEGORICAL_FEATURES = ["cpv_group", "contract_type", "procedure_type", "authority_type"]
NUMERIC_FEATURES = ["log_estimated_value", "publication_month", "log_history_contracts", "history_single_share"]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
MIN_HISTORY_CONTRACTS = 5


def add_authority_history(rows: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Add each authority's record from awards published strictly before the row's publication date.

    `rows` needs authority_cui and publication_date. `events` needs authority_cui,
    award_notice_date and is_single_offer. Later awards can't be known at publication.
    """
    past = events.dropna(subset=["authority_cui", "award_notice_date"]).sort_values("award_notice_date").copy()
    past["history_contracts"] = past.groupby("authority_cui").cumcount() + 1
    past["history_single"] = past.is_single_offer.astype(float).groupby(past.authority_cui).cumsum()
    original_order = rows.index
    ordered = rows.sort_values("publication_date")
    merged = pd.merge_asof(
        ordered,
        past[["authority_cui", "award_notice_date", "history_contracts", "history_single"]],
        left_on="publication_date",
        right_on="award_notice_date",
        by="authority_cui",
        allow_exact_matches=False,
        suffixes=("", "_history"),
    )
    merged.index = ordered.index
    result = rows.copy()
    result["history_contracts"] = merged.history_contracts.fillna(0).reindex(original_order)
    result["history_single"] = merged.history_single.fillna(0).reindex(original_order)
    return result


def build_features(rows: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Return the rows with the model's feature columns added."""
    result = add_authority_history(rows, events)
    value = result.estimated_value_ron.astype(float).where(lambda values: values >= 0)
    result["log_estimated_value"] = np.log1p(value)
    result["publication_month"] = result.publication_date.dt.month.astype(float)
    result["log_history_contracts"] = np.log1p(result.history_contracts)
    enough = result.history_contracts >= MIN_HISTORY_CONTRACTS
    result["history_single_share"] = (result.history_single / result.history_contracts).where(enough)
    for column in CATEGORICAL_FEATURES:
        result[column] = result[column].astype("object").where(result[column].notna(), "unknown").astype(str)
    return result


def assign_periods(rows: pd.DataFrame) -> pd.Series:
    """Give each contract the year its procedure first appeared.

    Contracts of one procedure share features and tend to share outcomes, and a framework can
    keep adding contracts for years. Splitting them across periods would leak the answer.
    """
    first_year = rows.first_file_order // 10
    procedure = rows.participation_notice_id.astype("object").where(rows.participation_notice_id.notna(), rows.award_notice_id)
    return first_year.groupby(procedure).transform("min")
