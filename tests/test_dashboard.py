import math
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.charts import segment_bars_html
from dashboard.data import MIN_AUTHORITY_CONTRACTS, MIN_CONTRACTS, compare_with_expected, period_share, segment_competition, wilson_interval, yearly_competition

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


def segments(*rows):
    return pd.DataFrame(rows, columns=["name", "contracts", "single_offer_share", "share_low", "share_high"])


def test_bars_show_the_whole_name_however_long_it_is():
    name = "Mobila (inclusiv mobila de birou), accesorii de mobilier, aparate de uz casnic si produse de curatat"
    html = segment_bars_html(segments((name, 200, 0.5, 0.4, 0.6)), "name", 0.25)
    assert f">{name}<" in html
    assert "…" not in html


def test_hovering_over_a_bar_gives_its_contracts_and_interval():
    html = segment_bars_html(segments(("Cluj", 2000, 0.5, 0.4, 0.6)), "name", 0.25)
    assert 'title="Cluj: 50.0% of 2,000 contracts. 95% interval: 40.0–60.0%"' in html


def test_names_are_escaped_so_they_cant_break_the_page():
    html = segment_bars_html(segments(('A<b>"x"', 200, 0.5, 0.4, 0.6)), "name", 0.25)
    assert "A<b>" not in html
    assert "A&lt;b&gt;" in html


def test_longest_bar_fills_the_scale_and_the_marker_is_proportional():
    html = segment_bars_html(segments(("A", 200, 0.5, 0.4, 0.6), ("B", 200, 0.25, 0.2, 0.3)), "name", 0.25)
    assert "width:100.00%" in html
    assert "width:50.00%" in html
    assert "left:50.00%" in html


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


def expected_rows(contracts, single, expected):
    return pd.DataFrame({"contracts": [contracts], "single_offer_contracts": [single], "expected_single_offers": [expected]})


def test_small_authorities_are_not_compared():
    assert compare_with_expected(expected_rows(MIN_AUTHORITY_CONTRACTS - 1, 5, 5)) is None


def test_comparison_reads_above_only_when_the_interval_clears_the_expectation():
    assert compare_with_expected(expected_rows(100, 60, 30))["reading"] == "above"
    assert compare_with_expected(expected_rows(100, 10, 30))["reading"] == "below"
    assert compare_with_expected(expected_rows(100, 32, 30))["reading"] == "in line with"


def test_scores_are_marked_as_unvalidated_and_the_test_result_is_shown(app):
    assert any("These scores are unvalidated" in item.value for item in app.warning)
    assert any("PR-AUC on the 2022 test" == item.label for item in app.metric)
