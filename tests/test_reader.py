import pandas as pd
import pytest

from src.reader import detect_format, read_table, sniff_csv_dialect


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


@pytest.mark.parametrize(
    "head,expected",
    [
        (b"PK\x03\x04" + b"\x00" * 26 + b"mimetypeapplication/vnd.oasis.opendocument.spreadsheet", "ods"),
        (b"PK\x03\x04" + b"\x00" * 26 + b"[Content_Types].xml", "xlsx"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "xls"),
        (b"\xef\xbb\xbfA|B\r\n1|2", "csv"),
    ],
)
def test_detects_format_from_content(head, expected):
    assert detect_format(head) == expected


@pytest.mark.parametrize(
    "line,expected",
    [
        ("A^B^C", ("^", '"')),
        ('A|B|C', ("|", '"')),
        ("A,B,C", (",", '"')),
        ("|A|,|B|,|C|", (",", "|")),
    ],
)
def test_sniffs_csv_dialect(line, expected):
    assert sniff_csv_dialect(line) == expected


def test_reads_pipe_csv_with_bom_as_strings(tmp_path):
    path = write(tmp_path, "a.csv", "﻿CUI|VAL\r\n\"0123\"|10\r\n".encode("utf-8"))
    df = read_table(path)
    assert list(df.columns) == ["CUI", "VAL"]
    assert df.loc[0, "CUI"] == "0123"


def test_reads_pipe_quoted_csv(tmp_path):
    path = write(tmp_path, "a.csv", b"|A|,|B|\n|x, y|,|2|\n")
    df = read_table(path)
    assert df.loc[0, "A"] == "x, y"


def test_reads_windows_1250_csv(tmp_path):
    path = write(tmp_path, "a.csv", "A^B\nFăget^1\n".encode("cp1250"))
    assert read_table(path).loc[0, "A"] == "Făget"


def write_workbook(path, sheets):
    with pd.ExcelWriter(path) as writer:
        for name, rows in sheets.items():
            pd.DataFrame(rows).to_excel(writer, sheet_name=name, header=False, index=False)


def test_skips_title_row_above_header(tmp_path):
    path = tmp_path / "a.xlsx"
    write_workbook(path, {"Sheet 1": [["Raport Trimestrul I", None], ["CUI", "VAL"], ["0123", "10"]]})
    df = read_table(path)
    assert list(df.columns) == ["CUI", "VAL"]
    assert df.loc[0, "CUI"] == "0123"


def test_joins_sheets_that_repeat_the_header(tmp_path):
    path = tmp_path / "a.xlsx"
    write_workbook(
        path,
        {"Sheet 1": [["CUI", "VAL"], ["1", "10"]], "Sheet 2": [["CUI", "VAL"], ["2", "20"]]},
    )
    df = read_table(path)
    assert df["CUI"].tolist() == ["1", "2"]
    assert df.attrs["sheets"] == 2


def test_ignores_legend_sheet_with_other_columns(tmp_path):
    path = tmp_path / "a.xlsx"
    write_workbook(
        path,
        {
            "Macheta": [["CUI", "VAL", "DATA"], ["1", "10", "x"]],
            "Legenda": [["Legenda Raport"], ["CUI"], ["VAL"]],
        },
    )
    df = read_table(path)
    assert list(df.columns) == ["CUI", "VAL", "DATA"]
    assert len(df) == 1


def test_keeps_repeated_column_names_apart(tmp_path):
    # Files from 2024 have two "Data publicare" columns: initiation and award.
    path = tmp_path / "a.xlsx"
    write_workbook(path, {"Sheet": [["Data publicare", "Data publicare"], ["2024", "2025"]]})
    df = read_table(path)
    assert list(df.columns) == ["Data publicare", "Data publicare.1"]
    assert df.loc[0, "Data publicare.1"] == "2025"


def test_reads_spreadsheet_whatever_the_extension_says(tmp_path):
    path = tmp_path / "wrong.ods"
    pd.DataFrame({"CUI": ["0123"]}).to_excel(tmp_path / "real.xlsx", index=False)
    path.write_bytes((tmp_path / "real.xlsx").read_bytes())
    assert read_table(path).loc[0, "CUI"] == "0123"
