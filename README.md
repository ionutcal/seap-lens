# SEAP Lens

A data warehouse, public dashboard and ML model built on Romanian public procurement data from SEAP/SICAP.

**This is an independent project, with no official link to SEAP, SICAP or any Romanian public authority.**

## Status

Work in progress. The data has been validated across all files from 2016 to 2026 Q3, and the warehouse builds locally on DuckDB. The move to AWS, the dashboard and the ML model are still to come.

- [Design spec](docs/superpowers/specs/2026-10-30-seap-lens-design.md)
- [Data validation report](docs/data-validation.md)

## Run locally

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```

Build the warehouse on the full data, which downloads about 2.4 GB:

```bash
.venv/bin/python -m scripts.download_raw
.venv/bin/python -m scripts.standardize_all
(cd dbt && ../.venv/bin/dbt build --profiles-dir .)
.venv/bin/python -m scripts.warehouse_summary
```

Files that can't be used as published are listed in `src/catalog.py`, and the reasons are in the [validation report](docs/data-validation.md).

## Data

Source: [data.gov.ro](https://data.gov.ro), published by the Autoritatea pentru Digitalizarea României. The 2025 dataset is licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
