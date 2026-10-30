"""Reads a SEAP file into a DataFrame of strings, whatever format it really is in."""

import io
from pathlib import Path

import pandas as pd

ODS_MIMETYPE = b"application/vnd.oasis.opendocument.spreadsheet"
OLE_MAGIC = b"\xd0\xcf\x11\xe0"
ZIP_MAGIC = b"PK\x03\x04"
SEPARATORS = ("^", "|", ",", ";")


def detect_format(head: bytes) -> str:
    """Return "ods", "xlsx", "xls" or "csv" from a file's first bytes."""
    if head.startswith(OLE_MAGIC):
        return "xls"
    if head.startswith(ZIP_MAGIC):
        return "ods" if ODS_MIMETYPE in head else "xlsx"
    return "csv"


def sniff_csv_dialect(header: str) -> tuple[str, str]:
    """Return (separator, quote character) from a CSV header line."""
    # The 2022 Q1 file uses "|" as the quote character: |A|,|B|.
    if header.startswith("|") and "|,|" in header:
        return ",", "|"
    return max(SEPARATORS, key=header.count), '"'


def _read_csv(path: Path) -> pd.DataFrame:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
        encoding = "utf-8"
    except UnicodeDecodeError:
        # Older exports are not UTF-8. See docs/data-validation.md.
        text = data.decode("cp1250", errors="replace")
        encoding = "cp1250"
    header = text.split("\n", 1)[0].rstrip("\r")
    separator, quote = sniff_csv_dialect(header)
    frame = pd.read_csv(
        io.StringIO(text),
        sep=separator,
        quotechar=quote,
        dtype=str,
        keep_default_na=False,
        na_values=[""],
        on_bad_lines="skip",
    )
    frame.attrs.update(encoding=encoding, separator=separator, sheets=1, lines=text.count("\n"))
    return frame


def _unique_names(names: list[str]) -> list[str]:
    # Keeps repeated headers apart the way pandas does: "Data", "Data.1".
    seen: dict[str, int] = {}
    unique = []
    for name in names:
        count = seen.get(name, 0)
        seen[name] = count + 1
        unique.append(name if count == 0 else f"{name}.{count}")
    return unique


def _with_header(sheet: pd.DataFrame) -> pd.DataFrame:
    """Use the first completely filled row as the header, skipping report titles."""
    filled = sheet.notna().sum(axis=1)
    header_index = filled[filled == sheet.shape[1]].index[0]
    names = _unique_names([str(value).strip() for value in sheet.loc[header_index]])
    return sheet.loc[header_index + 1 :].set_axis(names, axis=1)


def _read_spreadsheet(path: Path) -> pd.DataFrame:
    with path.open("rb") as handle:
        raw_sheets = pd.read_excel(
            handle, sheet_name=None, header=None, engine="calamine", dtype=str
        )
    sheets = [_with_header(sheet.dropna(axis=1, how="all")) for sheet in raw_sheets.values() if not sheet.empty]
    columns = list(sheets[0].columns)
    # Exports split at 65,000 rows repeat the header. Other sheets are legends.
    frames = [sheet for sheet in sheets if list(sheet.columns) == columns]
    frame = pd.concat(frames, ignore_index=True)
    frame.attrs.update(encoding=None, separator=None, sheets=len(frames), lines=None)
    return frame


def read_table(path: Path) -> pd.DataFrame:
    """Read a file by detecting its real format from its content, not its extension."""
    with path.open("rb") as handle:
        head = handle.read(4096)
    if detect_format(head) == "csv":
        return _read_csv(path)
    return _read_spreadsheet(path)
