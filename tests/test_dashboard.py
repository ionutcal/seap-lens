import math
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.data import MIN_CONTRACTS, period_share, segment_competition, shorten, wilson_interval, yearly_competition

APP = str(Path(__file__).parent.parent / "dashboard" / "app.py")


def test_wilson_interval_stays_inside_zero_and_one():
    low, high = wilson_interval(0, 10)
    assert low == 0
    assert 0 < high < 0.35
    low, high = wilson_interval(10, 10)
    assert high == 1
    assert 0.65 < low < 1


def test_wilson_interval_of_no_contracts_is_undefined():
    assert all(math.isnan(bound) for bound in wilson_interval(0, 0))


def test_long_labels_are_cut_at_a_word_with_an_ellipsis():
    assert shorten("Servicii de transport (cu exceptia transportului de deseuri)") == "Servicii de transport (cu…"
    assert shorten("Produse chimice") == "Produse chimice"


def frame(rows):
    return pd.DataFrame(rows, columns=["county", "year", "contracts", "single_offer_contracts"])


def test_yearly_share_includes_contracts_without_a_county():
    yearly = yearly_competition(frame([["Cluj", 2021, 100, 20], [None, 2021, 100, 40]]))
    assert yearly.single_offer_share.tolist() == [0.3]


def test_segments_use_only_the_period_and_sort_highest_first():
    rows = frame([["Cluj", 2020, 900, 900], ["Cluj", 2021, 200, 20], ["Iasi", 2021, 200, 60]])
    result = segment_competition(rows, "county", 2021, 2021)
    assert result.county.tolist() == ["Iasi", "Cluj"]
    assert result.single_offer_share.tolist() == [0.3, 0.1]


def test_segments_too_small_to_compare_are_left_out():
    rows = frame([["Cluj", 2021, MIN_CONTRACTS - 1, 50], ["Iasi", 2021, MIN_CONTRACTS, 50], [None, 2021, 900, 50]])
    assert segment_competition(rows, "county", 2021, 2021).county.tolist() == ["Iasi"]


def test_period_share_weighs_by_contracts_not_by_year():
    rows = frame([["Cluj", 2021, 100, 50], ["Cluj", 2022, 300, 0]])
    assert period_share(rows, 2021, 2022) == pytest.approx(0.125)


@pytest.fixture(scope="module")
def app():
    return AppTest.from_file(APP, default_timeout=60).run()


def test_app_runs_without_errors_on_the_committed_extract(app):
    assert not app.exception


def test_app_says_it_is_independent_and_that_one_offer_is_not_wrongdoing(app):
    text = " ".join(item.value for item in [*app.caption, *app.markdown])
    assert "no official link to SEAP" in text
    assert "does not mean wrongdoing" in text


def test_totals_are_marked_as_not_verified(app):
    assert any("not been compared with an official figure" in item.value for item in app.warning)
