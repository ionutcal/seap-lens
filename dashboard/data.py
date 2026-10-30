"""Reads the dashboard's Parquet extract and prepares it for the views."""

import json
import math
import os
from pathlib import Path

import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).parent / "data"
# Below this, a share moves too much by chance to compare groups.
MIN_CONTRACTS = 100
# Long labels leave no room for the bars on a phone.
MAX_LABEL_LENGTH = 32


def shorten(label: str) -> str:
    """Cut a long label at a word boundary. Tables keep the full name."""
    if len(label) <= MAX_LABEL_LENGTH:
        return label
    return label[:MAX_LABEL_LENGTH].rsplit(" ", 1)[0].rstrip(" ,;") + "…"


def data_dir() -> Path:
    return Path(os.environ.get("DASHBOARD_DATA_DIR", DEFAULT_DATA_DIR))


def load_table(name: str) -> pd.DataFrame:
    return pd.read_parquet(data_dir() / f"{name}.parquet")


def load_metadata() -> dict:
    return json.loads((data_dir() / "metadata.json").read_text())


def wilson_interval(successes: float, total: float, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a share, reliable for small groups and extreme shares."""
    if total == 0:
        return (math.nan, math.nan)
    share = successes / total
    denominator = 1 + z**2 / total
    center = (share + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(share * (1 - share) / total + z**2 / (4 * total**2)) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def with_shares(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the single-offer share and its confidence interval to a grouped table."""
    result = frame.copy()
    result["single_offer_share"] = result.single_offer_contracts / result.contracts
    intervals = [wilson_interval(s, n) for s, n in zip(result.single_offer_contracts, result.contracts)]
    result["share_low"] = [low for low, _ in intervals]
    result["share_high"] = [high for _, high in intervals]
    return result


def yearly_competition(by_county: pd.DataFrame) -> pd.DataFrame:
    """National single-offer share per year."""
    totals = by_county.groupby("year", as_index=False)[["contracts", "single_offer_contracts"]].sum()
    return with_shares(totals.sort_values("year"))


def segment_competition(frame: pd.DataFrame, column: str, first_year: int, last_year: int) -> pd.DataFrame:
    """Share per county or CPV group over a period, leaving out groups too small to compare."""
    period = frame[frame.year.between(first_year, last_year) & frame[column].notna()]
    grouped = period.groupby(column, as_index=False)[["contracts", "single_offer_contracts"]].sum()
    grouped = grouped[grouped.contracts >= MIN_CONTRACTS]
    return with_shares(grouped).sort_values("single_offer_share", ascending=False).reset_index(drop=True)


def period_share(frame: pd.DataFrame, first_year: int, last_year: int) -> float:
    period = frame[frame.year.between(first_year, last_year)]
    return period.single_offer_contracts.sum() / period.contracts.sum()


def yearly_contracted_value(value: pd.DataFrame) -> pd.DataFrame:
    return value.groupby("year", as_index=False)[["contracted_value_ron", "contracts", "suspect_contracts"]].sum()
