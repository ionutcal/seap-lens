import pandas as pd
import pytest

from src.dates import parse_dates


def parsed(values):
    return parse_dates(pd.Series(values)).dt.strftime("%Y-%m-%d").tolist()


def test_iso_dates_with_any_precision():
    assert parsed(["2016-01-04 10:07:05.817000000", "2017-01-14 01:30:00.517", "2024-07-01 06:36:39"]) == [
        "2016-01-04", "2017-01-14", "2024-07-01",
    ]


def test_excel_serial_numbers():
    assert parsed(["45017.45884259259"]) == ["2023-04-01"]


def test_month_first_is_inferred_when_the_second_field_exceeds_twelve():
    assert parsed(["04/02/2018", "04/25/2018"]) == ["2018-04-02", "2018-04-25"]


def test_day_first_is_inferred_when_the_first_field_exceeds_twelve():
    assert parsed(["03-04-2018 14:34:57", "25-04-2018 09:00:00"]) == ["2018-04-03", "2018-04-25"]
    assert parsed(["1/7/2021", "25/7/2021"]) == ["2021-07-01", "2021-07-25"]
    assert parsed(["01.07.2019 07:34:06", "31.07.2019 07:34:06"]) == ["2019-07-01", "2019-07-31"]


def test_twelve_hour_clock_with_month_first():
    assert parsed(["7/1/2023 9:00:06 AM", "7/25/2023 1:00:06 PM"]) == ["2023-07-01", "2023-07-25"]


def test_text_that_is_not_a_date_becomes_null():
    result = parse_dates(pd.Series(["DATA_ANUNT_ATRIBUIRE", "2024-07-01 06:36:39", None, "7"]))
    assert result.isna().tolist() == [True, False, True, True]


def test_small_numbers_are_not_read_as_excel_dates():
    assert parse_dates(pd.Series(["7", "12345"])).isna().all()
