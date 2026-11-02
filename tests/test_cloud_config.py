"""Checks that the cloud configuration agrees with the code, with no AWS account."""

import json
import subprocess
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from src.schema import CONTRACT_ALIASES, NOTICE_ALIASES, standardize
from src.standardize import clean, save_parquet

ROOT = Path(__file__).parent.parent
GLUE_COLUMNS = json.loads((ROOT / "infra" / "glue_columns.json").read_text())
GLUE_TYPES = {"string": "string", "large_string": "string", "double": "double", "int64": "bigint", "timestamp[us]": "timestamp"}


def standardized_schema(kind, raw_row, tmp_path):
    typed, rejects = clean(standardize(pd.DataFrame([raw_row]), kind), kind)
    assert rejects.empty
    typed["file_year"], typed["file_period"], typed["source_sha256"] = 2023, "Q1", "x"
    path = tmp_path / f"{kind}.parquet"
    save_parquet(typed, path)
    return {field.name: GLUE_TYPES[str(field.type)] for field in pq.read_schema(path)}


def test_glue_contract_columns_match_what_standardization_writes(tmp_path):
    row = {"Numar anunt atribuire": "CAN1", "Data anunt atribuire": "2023-01-01 10:00:00", "Tip contract": "Furnizare",
           "Numar oferte": "3", "Valoare contract (RON)": "100", "Valoare estimata": "200"}
    assert standardized_schema("contracts", row, tmp_path) == GLUE_COLUMNS["contracts"]


def test_glue_notice_columns_match_what_standardization_writes(tmp_path):
    row = {"Numar anunt initiere": "CN1", "Data publicare": "2023-01-01 10:00:00", "Valoare estimata": "5"}
    assert standardized_schema("notices", row, tmp_path) == GLUE_COLUMNS["notices"]


def test_every_canonical_column_reaches_glue():
    assert set(CONTRACT_ALIASES) <= set(GLUE_COLUMNS["contracts"])
    assert set(NOTICE_ALIASES) <= set(GLUE_COLUMNS["notices"])


def test_nothing_private_is_committed_with_the_terraform_config():
    # They exist on the machine that runs Terraform, so what matters is that Git doesn't track them.
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert not [path for path in tracked if path.endswith(".tfvars") or ".tfstate" in path]
