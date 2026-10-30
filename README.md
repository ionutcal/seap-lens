# SEAP Lens

A data warehouse, public dashboard and ML model built on Romanian public procurement data from SEAP/SICAP.

**This is an independent project, with no official link to SEAP, SICAP or any Romanian public authority.**

**Live dashboard: [seap-lens.streamlit.app](https://seap-lens.streamlit.app/)**

## Status

Work in progress. The data has been validated across all files from 2016 to 2026 Q3, the warehouse builds locally on DuckDB, and the dashboard is public. The model is trained, tested and shown in the dashboard. The move to AWS is still to come.

- [Design spec](docs/superpowers/specs/2026-10-30-seap-lens-design.md)
- [Data validation report](docs/data-validation.md)
- [Model results](docs/model-results.md)

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

Run the dashboard, which reads the extract committed in `dashboard/data`:

```bash
.venv/bin/streamlit run dashboard/app.py
```

After rebuilding the warehouse, refresh that extract with `.venv/bin/python -m scripts.export_dashboard`.

Train and test the model, on macOS after `brew install libomp`. The test runs only once, and its result is committed:

```bash
.venv/bin/pip install -r requirements-ml.txt
.venv/bin/python -m scripts.train_model validate
.venv/bin/python -m scripts.train_model test
.venv/bin/python -m scripts.train_model score
```

Files that can't be used as published are listed in `src/catalog.py`, and the reasons are in the [validation report](docs/data-validation.md).

## Data

Source: [data.gov.ro](https://data.gov.ro), published by the Autoritatea pentru Digitalizarea României. Datasets from 2016–2020 are under OGL-ROU-1.0 and those from 2021 under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The figures here are derived from that data.
