"""Turns one file's canonical columns into typed rows, plus rejected rows with a reason."""

import re
from pathlib import Path

import pandas as pd

from src.dates import parse_dates

CONTRACT_TYPES = {"Furnizare", "Servicii", "Lucrari"}
NOTICE_ID = re.compile(r"^[A-Z]*\d+$")
DATE_COLUMNS = {
    "contracts": ["award_notice_date", "participation_notice_date", "contract_date"],
    "notices": ["notice_date"],
}
NUMBER_COLUMNS = {
    "contracts": ["value_ron", "bid_count", "estimated_value"],
    "notices": ["estimated_value", "lot_value"],
}
# Spreadsheets store these as numbers, so the same value can read "12" or "12.0".
INTEGER_TEXT_COLUMNS = ["contract_number", "lot_number"]
ID_COLUMNS = {
    "contracts": ["award_notice_id", "participation_notice_id"],
    "notices": ["notice_id"],
}


def parse_number(series: pd.Series) -> pd.Series:
    """Parse numbers, including thousands commas. Anything else becomes NaN."""
    text = series.astype("object").where(series.notna(), None).map(
        lambda value: None if value is None else str(value).strip()
    )
    # Files from 2023 Q4 and 2024 Q2 write 417185 as "417,185".
    thousands = text.str.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", na=False)
    text = text.where(~thousands, text.str.replace(",", "", regex=False))
    return pd.to_numeric(text, errors="coerce")


def _strip_float_suffix(series: pd.Series) -> pd.Series:
    return series.astype("object").map(
        lambda value: value if pd.isna(value) else re.sub(r"\.0$", "", str(value).strip()),
        na_action=None,
    )


def _valid_id(series: pd.Series) -> pd.Series:
    return series.map(lambda value: bool(NOTICE_ID.match(value)) if isinstance(value, str) else False)


def clean(frame: pd.DataFrame, kind: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (typed rows, rejected rows with a reject_reason column)."""
    frame = frame.astype("object").where(frame.notna(), None).copy()
    frame = frame.map(lambda value: None if isinstance(value, str) and value.strip().upper() == "NULL" else value)
    for column in ID_COLUMNS[kind]:
        if column in frame:
            frame[column] = frame[column].map(lambda value: value.strip().upper() if isinstance(value, str) else value)

    reasons = pd.Series(pd.NA, index=frame.index, dtype="object")
    if kind == "contracts":
        reasons = reasons.mask(~_valid_id(frame["award_notice_id"]), "invalid_award_notice_id")
        contract_type = frame["contract_type"].map(lambda v: v.strip() if isinstance(v, str) else v)
        reasons = reasons.mask(reasons.isna() & contract_type.notna() & ~contract_type.isin(CONTRACT_TYPES), "unknown_contract_type")
        bids = parse_number(frame["bid_count"])
        reasons = reasons.mask(reasons.isna() & frame["bid_count"].notna() & bids.isna(), "invalid_bid_count")
    else:
        reasons = reasons.mask(~_valid_id(frame["notice_id"]), "invalid_notice_id")

    rejected = reasons.notna()
    rejects = frame[rejected].copy()
    rejects["reject_reason"] = reasons[rejected]
    result = frame[~rejected].copy()

    for column in DATE_COLUMNS[kind]:
        if column in result:
            result[column] = parse_dates(result[column])
    for column in NUMBER_COLUMNS[kind]:
        if column in result:
            result[column] = parse_number(result[column])
    for column in INTEGER_TEXT_COLUMNS:
        if column in result:
            result[column] = _strip_float_suffix(result[column])
    return result.reset_index(drop=True), rejects.reset_index(drop=True)


def save_parquet(frame: pd.DataFrame, path: Path) -> None:
    """Write rows with text columns typed as strings, even when a column is entirely empty."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.attrs = {}
    frame.astype({column: "string" for column in frame.columns if frame[column].dtype == object}).to_parquet(
        path, index=False, coerce_timestamps="us", allow_truncated_timestamps=True
    )
