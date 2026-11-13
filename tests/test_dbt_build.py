"""Builds the dbt project on a small dataset that exercises each rule, then checks the marts."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from src.sample_data import write_sample_data

DBT_DIR = Path(__file__).parent.parent / "dbt"


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    root = tmp_path_factory.mktemp("warehouse")
    write_sample_data(root)
    database = root / "warehouse.duckdb"
    environment = {**os.environ, "SEAP_DATA_DIR": str(root), "SEAP_DB": str(database)}
    dbt = shutil.which("dbt", path=str(Path(sys.executable).parent)) or "dbt"
    result = subprocess.run(
        [dbt, "build", "--profiles-dir", ".", "--target-path", str(root / "target"), "--log-path", str(root / "logs")],
        cwd=DBT_DIR, env=environment, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout
    connection = duckdb.connect(str(database), read_only=True)
    yield connection
    connection.close()


def scalar(connection, query):
    return connection.execute(query).fetchone()[0]


def test_republished_contract_keeps_only_its_latest_value(warehouse):
    assert warehouse.execute("select value_ron from fct_awards where award_notice_id = 'CAN1'").fetchall() == [(2000.0,)]


def test_republished_contract_keeps_its_contract_year(warehouse):
    assert scalar(warehouse, "select contract_year from fct_awards where award_notice_id = 'CAN1'") == 2023


def test_contracted_value_counts_joint_winners_once_and_skips_ceilings_and_suspects(warehouse):
    standalone = scalar(warehouse, "select contracted_value_ron from mart_contracted_value where value_kind = 'standalone_contract'")
    assert standalone == 2000 + 500
    subsequent = scalar(warehouse, "select contracted_value_ron from mart_contracted_value where value_kind = 'subsequent_contract'")
    assert subsequent == 100


def test_values_far_above_the_limit_or_the_estimate_are_suspect(warehouse):
    assert scalar(warehouse, "select is_suspect_value from fct_awards where award_notice_id = 'CAN5'") is True
    assert scalar(warehouse, "select is_suspect_value from fct_awards where award_notice_id = 'CAN6'") is True
    assert scalar(warehouse, "select is_suspect_value from fct_awards where award_notice_id = 'CAN2' limit 1") is False


def test_single_offer_needs_every_row_to_agree(warehouse):
    flag = "select is_single_offer from fct_contract_competition where award_notice_id = '{}'"
    assert scalar(warehouse, flag.format("CAN7")) is True
    assert scalar(warehouse, flag.format("CAN8")) is False


def test_contracts_without_bid_counts_have_a_null_label(warehouse):
    assert scalar(warehouse, "select bid_count from fct_contract_competition where award_notice_id = 'CAN1'") is None


def test_negotiation_without_notice_stays_out_of_authority_competition(warehouse):
    assert scalar(warehouse, "select contracts from mart_authority_competition where year = 2021") == 2


def test_lot_level_notices_become_one_procedure(warehouse):
    assert scalar(warehouse, "select count(*) from fct_procedures where notice_id = 'CN6'") == 1


def test_county_comes_from_notices(warehouse):
    assert scalar(warehouse, "select county from dim_authority where authority_cui = '9'") == "Cluj"


def test_docs_site_builds_on_the_sample_data(tmp_path):
    from scripts.build_docs import main as build_docs

    sys.argv = ["build_docs", str(tmp_path / "site")]
    build_docs()
    page = (tmp_path / "site" / "index.html").read_text()
    assert "fct_contract_competition" in page
    assert "framework_ceiling (not spending)" in page
