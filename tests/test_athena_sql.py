"""Compiles the dbt project for Athena and parses the SQL as Trino, with no AWS account or connection."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sqlglot = pytest.importorskip("sqlglot")
pytest.importorskip("dbt.adapters.athena")

DBT_DIR = Path(__file__).parent.parent / "dbt"
DUCKDB_ONLY = ("any_value(", "arg_max(", "generate_series(", "median(", "read_parquet(", " exclude (")


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    target = tmp_path_factory.mktemp("athena")
    environment = {
        **os.environ, "AWS_ACCESS_KEY_ID": "unused", "AWS_SECRET_ACCESS_KEY": "unused", "SEAP_BUCKET": "example",
        "AWS_ENDPOINT_URL": "http://127.0.0.1:9", "AWS_MAX_ATTEMPTS": "1",
    }
    dbt = shutil.which("dbt", path=str(Path(sys.executable).parent)) or "dbt"
    result = subprocess.run(
        [dbt, "--no-partial-parse", "--no-use-colors", "compile", "--profiles-dir", ".", "--target", "athena",
         "--no-populate-cache", "--no-introspect", "--target-path", str(target), "--log-path", str(target / "logs")],
        cwd=DBT_DIR, env=environment, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout[-3000:]
    return sorted((target / "compiled").rglob("*.sql"))


def test_every_model_and_test_compiled(compiled):
    names = {path.stem for path in compiled}
    assert {"fct_awards", "dim_date", "ml_contract_units", "every_source_contract_reaches_fct_awards"} <= names


def test_compiled_sql_parses_as_trino(compiled):
    for path in compiled:
        sqlglot.parse_one(path.read_text(), read="trino")


def test_compiled_sql_has_no_duckdb_functions(compiled):
    for path in compiled:
        text = path.read_text().lower()
        assert not [token for token in DUCKDB_ONLY if token in text], path.name
