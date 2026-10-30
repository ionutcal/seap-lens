"""Builds the dbt project on a small dataset that exercises each rule, then checks the marts."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src.schema import standardize
from src.standardize import clean, save_parquet

DBT_DIR = Path(__file__).parent.parent / "dbt"


def contract(notice, number, winner="1", value="100", through="Fara acord cadru", bids=None, date="2023-05-01 00:00:00",
             procedure="Licitatie deschisa", participation=None):
    return {
        "Numar anunt atribuire": notice, "Data anunt atribuire": date, "Numar anunt initiere": participation,
        "Data contract": date, "Numar contract": number, "Numar lot": "1", "Tip contract": "Furnizare",
        "Tip procedura": procedure, "Incheiat prin": through, "CUI autoritate contractanta": "RO 9",
        "Autoritate contractanta": "Primaria", "CUI ofertant castigator": winner, "Ofertant castigator": f"Firma {winner}",
        "Valoare contract (RON)": value, "Numar oferte": bids, "Cod CPV": "33600000-6", "Denumire CPV": "Medicamente",
    }


def notice(identifier, value="5", county="Cluj"):
    return {
        "Numar anunt initiere": identifier, "Data publicare": "2023-01-02 10:00:00",
        "CUI autoritate contractanta": "9", "Autoritate contractanta": "Primaria", "Judet": county,
        "Tip contract": "Furnizare", "Tip procedura": "Licitatie deschisa", "Valoare estimata": value, "Moneda": "RON",
        "Cod CPV": "33600000-6", "Denumire CPV": "Medicamente",
    }


CONTRACT_FILES = {
    (2021, "Q1"): [
        contract("CAN7", "7", bids="1", date="2021-02-01 00:00:00"),
        contract("CAN7", "7", winner="2", bids="1", date="2021-02-01 00:00:00"),
        contract("CAN8", "8", bids="1", date="2021-02-01 00:00:00"),
        contract("CAN8", "8", winner="2", bids="3", date="2021-02-01 00:00:00"),
        contract("CAN9", "9", bids="1", date="2021-02-01 00:00:00", procedure="Negociere fara anunt de participare"),
    ],
    (2023, "Q3"): [
        contract("CAN1", "1", value="1,000"),
        contract("CAN2", "2", winner="1", value="500"),
        contract("CAN2", "2", winner="2", value="500"),
        contract("CAN3", "3", value="9000000000", through="Cu acord cadru"),
        contract("CAN4", "4", value="100", through="Cu acord cadru subsecvent"),
        contract("CAN5", "5", value="200000000000"),
        contract("CAN6", "6", value="1000", participation="CN6"),
    ],
    # CAN1 is republished with a new value, and a 2023 contract appears in a later file.
    (2024, "Q1"): [contract("CAN1", "1", value="2000")],
}
NOTICE_FILES = {(2023, "Q3"): [notice("CN6", value="10"), notice("CN6", value="10")]}


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    root = tmp_path_factory.mktemp("warehouse")
    for kind, files in (("contracts", CONTRACT_FILES), ("notices", NOTICE_FILES)):
        for (year, period), rows in files.items():
            typed, rejects = clean(standardize(pd.DataFrame(rows), kind), kind)
            assert rejects.empty
            typed["file_year"], typed["file_period"], typed["source_sha256"] = year, period, "x"
            save_parquet(typed, root / "standard" / kind / f"{year}_{period}.parquet")
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
