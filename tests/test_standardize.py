import pandas as pd
import pytest

from src.standardize import clean, parse_number


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("417,185", 417185.0),
        ("1,234,567.50", 1234567.5),
        ("2175.0", 2175.0),
        ("2175", 2175.0),
        ("-5", -5.0),
    ],
)
def test_parses_numbers(raw, expected):
    assert parse_number(pd.Series([raw])).iloc[0] == expected


@pytest.mark.parametrize("raw", ["NULL", "text", "1,23", "", None])
def test_other_values_are_not_numbers(raw):
    assert parse_number(pd.Series([raw], dtype="object")).isna().all()


def contract(**overrides):
    row = {
        "award_notice_id": "CAN1",
        "award_notice_date": "2023-01-02 10:00:00",
        "participation_notice_id": "CN1",
        "participation_notice_date": "2022-12-01 10:00:00",
        "contract_date": "2023-01-01 00:00:00",
        "contract_number": "12.0",
        "lot_number": "1.0",
        "contract_type": "Furnizare",
        "value_ron": "1,000",
        "bid_count": "3",
        "estimated_value": "NULL",
        "winner_cui": "RO 1",
    }
    return {**row, **overrides}


def run(rows, kind="contracts"):
    return clean(pd.DataFrame(rows), kind)


def test_clean_casts_values_and_identifiers():
    result, rejects = run([contract()])
    row = result.iloc[0]
    assert rejects.empty
    assert row.value_ron == 1000.0
    assert row.bid_count == 3
    assert pd.isna(row.estimated_value)
    assert row.contract_number == "12"
    assert row.lot_number == "1"
    assert row.award_notice_date == pd.Timestamp("2023-01-02 10:00:00")


def test_null_text_becomes_a_real_null():
    result, _ = run([contract(participation_notice_id="NULL")])
    assert pd.isna(result.iloc[0].participation_notice_id)


@pytest.mark.parametrize(
    "bad,reason",
    [
        ({"award_notice_id": "NUMAR_ANUNT_ATRIBUIRE"}, "invalid_award_notice_id"),
        ({"award_notice_id": None}, "invalid_award_notice_id"),
        ({"contract_type": "TIP_CONTRACT"}, "unknown_contract_type"),
        ({"bid_count": "Contract de lucrari in zona centrala"}, "invalid_bid_count"),
    ],
)
def test_rows_that_are_not_contracts_go_to_rejects_with_a_reason(bad, reason):
    result, rejects = run([contract(), contract(**bad)])
    assert len(result) == 1
    assert rejects.reject_reason.tolist() == [reason]


def test_missing_bid_count_is_not_a_reject():
    result, rejects = run([contract(bid_count=None)])
    assert rejects.empty
    assert pd.isna(result.iloc[0].bid_count)


def test_clean_notices_rejects_footers():
    rows = [
        {"notice_id": "CN1", "notice_date": "2023-01-02 10:00:00", "estimated_value": "5", "contract_type": "Lucrari"},
        {"notice_id": "(4 row(s) affected)", "notice_date": None, "estimated_value": None, "contract_type": None},
    ]
    result, rejects = run(rows, "notices")
    assert result.notice_id.tolist() == ["CN1"]
    assert rejects.reject_reason.tolist() == ["invalid_notice_id"]
    assert result.iloc[0].estimated_value == 5.0
