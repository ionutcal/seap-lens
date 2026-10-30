import pandas as pd
import pytest

from src.schema import normalize_cui, standardize


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("RO 8955860", "8955860"),
        ("RO8955860", "8955860"),
        ("ro 8955860", "8955860"),
        ("8955860", "8955860"),
        ("4453144.0", "4453144"),
        (" 123 ", "123"),
        ("", None),
        (None, None),
        ("BE0404616494", "BE0404616494"),
    ],
)
def test_normalizes_tax_codes(raw, expected):
    assert normalize_cui(raw) == expected


def test_maps_old_and_new_contract_columns_to_the_same_names():
    old = pd.DataFrame({"NumarOfertePrimite": ["3"], "CastigatorCUI": ["RO 1"], "ValoareRON": ["10"]})
    new = pd.DataFrame({"Numar oferte": ["3"], "CUI castigator": ["RO 1"], "Valoare contract (RON)": ["10"]})
    for frame in (old, new):
        result = standardize(frame, "contracts")
        assert result.loc[0, "bid_count"] == "3"
        assert result.loc[0, "winner_cui"] == "1"
        assert result.loc[0, "value_ron"] == "10"


def test_second_publication_date_is_the_award_date():
    frame = pd.DataFrame({"Data publicare": ["2024-01-01"], "Data publicare.1": ["2024-06-01"]})
    result = standardize(frame, "contracts")
    assert result.loc[0, "participation_notice_date"] == "2024-01-01"
    assert result.loc[0, "award_notice_date"] == "2024-06-01"


def test_old_contract_currency_is_not_read_as_the_estimate_currency():
    frame = pd.DataFrame({"Moneda": ["EUR"], "MonedaValoareEstimataParticipare": ["RON"]})
    assert standardize(frame, "contracts").loc[0, "estimated_currency"] == "RON"


def test_late_2022_currency_column_is_the_estimate_currency():
    frame = pd.DataFrame({"Moneda": ["EUR"], "Valoare estimata": ["5"]})
    assert standardize(frame, "contracts").loc[0, "estimated_currency"] == "EUR"


def test_unknown_column_fails_loudly():
    with pytest.raises(ValueError, match="Coloana Noua"):
        standardize(pd.DataFrame({"Coloana Noua": ["x"]}), "contracts")


def test_missing_canonical_columns_stay_null():
    result = standardize(pd.DataFrame({"CUI_AC": ["1"]}), "contracts")
    assert result["bid_count"].isna().all()
