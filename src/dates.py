"""Parses the date formats found in SEAP files.

Each file uses one convention, but the convention changes between files, so day-first or
month-first has to be inferred per file: "04/02/2018" alone cannot be resolved.
"""

import pandas as pd

EXCEL_EPOCH = "1899-12-30"
# Excel serials for 2000-01-01 and 2100-01-01. Anything else numeric is not a date.
EXCEL_SERIAL_RANGE = (36526, 73051)


def _is_day_first(values: pd.Series) -> bool:
    fields = values.str.extract(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-]\d{4}").dropna()
    if fields.empty:
        return False
    return int(fields[0].astype(int).max()) > 12


def parse_dates(series: pd.Series) -> pd.Series:
    """Parse one file's date column. Values that are not dates become NaT."""
    values = series.astype("object").where(series.notna(), None).map(
        lambda value: None if value is None else str(value).strip()
    )
    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    text = values.dropna().astype(str)

    iso = text[text.str.match(r"^\d{4}-\d{2}-\d{2}")]
    result.loc[iso.index] = pd.to_datetime(iso.str.slice(0, 19), errors="coerce", format="%Y-%m-%d %H:%M:%S")
    date_only = iso[iso.str.len() == 10]
    result.loc[date_only.index] = pd.to_datetime(date_only, errors="coerce", format="%Y-%m-%d")

    numeric = pd.to_numeric(text[text.str.match(r"^\d+(\.\d+)?$")], errors="coerce")
    serial = numeric[numeric.between(*EXCEL_SERIAL_RANGE)]
    result.loc[serial.index] = pd.to_datetime(serial, unit="D", origin=EXCEL_EPOCH)

    separated = text[text.str.match(r"^\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}")]
    if not separated.empty:
        result.loc[separated.index] = pd.to_datetime(
            separated.str.replace(r"[.\-]", "/", n=2, regex=True),
            errors="coerce",
            format="mixed",
            dayfirst=_is_day_first(separated),
        )
    return result
