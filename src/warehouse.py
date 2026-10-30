"""Runs read-only queries against the warehouse, on DuckDB locally or Athena in the cloud."""

import os

import pandas as pd

LOCAL_DATABASE = "../data/warehouse.duckdb"


def query(sql: str) -> pd.DataFrame:
    if os.environ.get("SEAP_WAREHOUSE", "duckdb") == "athena":
        return _query_athena(sql)
    return _query_duckdb(sql)


def _query_duckdb(sql: str) -> pd.DataFrame:
    import duckdb

    # Staging views read Parquet through paths relative to the dbt folder.
    previous = os.getcwd()
    os.chdir("dbt")
    try:
        with duckdb.connect(LOCAL_DATABASE, read_only=True) as connection:
            return connection.execute(sql).df()
    finally:
        os.chdir(previous)


def _query_athena(sql: str) -> pd.DataFrame:
    from pyathena import connect
    from pyathena.pandas.cursor import PandasCursor

    connection = connect(
        s3_staging_dir=f"s3://{os.environ['SEAP_BUCKET']}/athena-results/",
        region_name=os.environ.get("AWS_REGION", "eu-central-1"),
        work_group=os.environ.get("SEAP_WORKGROUP", "seap-lens"),
        schema_name=os.environ.get("SEAP_DBT_SCHEMA", "seap_lens_marts"),
        cursor_class=PandasCursor,
    )
    with connection.cursor() as cursor:
        return cursor.execute(sql).as_pandas()
