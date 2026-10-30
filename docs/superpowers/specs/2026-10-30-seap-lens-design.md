# SEAP Lens: Design Spec

**Date:** 2026-10-30
**Status:** Approved, updated after data validation
**Repository name:** `seap-lens`

## 1. Purpose

SEAP Lens is a portfolio project that turns Romanian public procurement data from SEAP/SICAP into a cloud data warehouse, a public dashboard and one integrated ML model.

It exists to close specific gaps on George Ionuț Călin's CV: cloud (AWS), orchestration (Airflow), dbt, dimensional modelling, infrastructure as code (Terraform) and applied ML in a data system. The assumed target is a Data Engineer or hybrid data role.

SEAP Lens is an independent project with no official link to SEAP, SICAP or any Romanian public authority. The README and the dashboard must both say so.

### Definition of done

- The dashboard is public and works with no AWS resources running.
- The pipeline can be rebuilt from the repository, with documented steps.
- CI passes, and dbt tests pass on the full dataset.
- The model's test result on 2022 Q2–Q4 is published whatever it turns out to be, next to the simple baseline.
- The README states the limits openly: bid counts missing after 2022 and in two earlier quarters, unvalidated scores from 2023 onwards, spending totals available only from 2023, and the choice of Airflow for quarterly data.

### Success test

A recruiter can open the dashboard and understand the findings within a few minutes. An engineer can find orchestration, tests and reproducible infrastructure in the repository.

## 2. Data

**Source:** yearly "Achiziții publice" datasets from the Autoritatea pentru Digitalizarea României on data.gov.ro, listed through its CKAN API. Datasets from 2016–2020 are under OGL-ROU-1.0 and those from 2021 under CC BY 4.0. The dashboard and the README attribute the source.

The full findings are in the [data validation report](../../data-validation.md). The ones that shape this design:

- **Volume:** 80 usable files, 2.40 GB raw, with 3,986,575 contract rows and 304,514 notice rows, from 2016 to 2026 Q3.
- **Bid counts:** present from 2016 to 2022 Q4. Missing in 2022 Q1 and from 2023 onwards. 2019 Q2 is also missing, because its file is a copy of 2019 Q3. That leaves 557,340 usable labels.
- **Republication:** the same contract rows appear in several files, and 7.7% of republished contracts change value. The 4.0 million rows reduce to 2.18 million awards.
- **Format drift:** 158 contract and 96 notice column names, several date conventions that change between files, thousands commas in two quarters, mixed encodings, and spreadsheets split across sheets.
- **Wrong files:** the 2024 Q1 contract CSV is truncated, and the 2017 Q1 notice file holds dates from 2015.
- **Value outliers:** some values look like entry errors, including one 125.9 billion RON contract in 2025.

## 3. Scope

**In scope**

- Contract files and initiation notices, from 2016 to the present.
- A warehouse with tested dimensional marts.
- A public dashboard.
- One ML model that predicts single-offer contracts.

**Out of scope**

- Direct purchases and contract modification files. These can be added later.
- Years 2007–2015, which the model does not need.
- Spark and streaming, because the volume and the quarterly updates do not call for them.
- Currency conversion. Non-RON estimated values stay `NULL`.
- History tracking for dimensions.
- Real-time model serving and periodic retraining.

## 4. Architecture

```text
data.gov.ro
    │  monthly check for new files
    ▼
S3 raw            original files, unchanged
    ▼
Standardization   Python: one schema across all format generations
    ▼
S3 Parquet        uniform columns, partitioned by year and quarter
    ▼
Athena + dbt      staging → intermediate → marts, with tests
    ├──► ML model     training once, scoring monthly, results in S3
    ▼
Parquet export    copied outside AWS
    ▼
Public Streamlit dashboard
```

### Components

| Component | Responsibility |
|---|---|
| Ingestion | Lists files through the data.gov.ro API, downloads only new or changed ones, and stores them in S3 raw |
| Standardization | Detects each file's real format, maps it to one schema, parses dates per file, and validates rows |
| dbt on Athena | Cleans data, deduplicates across files, resolves suppliers by tax code, and builds marts |
| ML | Trains and evaluates once, then scores new notices and monitors drift |
| Airflow | Runs the steps in order, with retries |
| Terraform | Creates S3, EC2, IAM, schedules, the stop guard, and cost controls |
| Dashboard | Reads an exported Parquet file and has no runtime dependency on AWS |

### Key decisions

- **Cloud:** AWS only. It came from job ads the author saw. Multi-cloud would double the work without adding much.
- **Warehouse:** Athena over S3. Redshift requires a paid plan.
- **Orchestration:** self-hosted Airflow in Docker Compose on EC2. Managed Airflow (MWAA) is not supported on this account type.
- **EC2 runtime:** a schedule starts the instance monthly and the instance stops after the run. A separate rule force-stops it after 4 hours, a starting value to adjust once real run times are known.
- **Idempotency:** each source file is identified by content hash, so repeated runs do not duplicate data.
- **MLflow:** runs on the EC2 instance, with results stored in S3 so they survive instance stops.
- **Trade-off stated openly:** for quarterly data, a scheduled job would be enough. Airflow was chosen to learn and demonstrate it, and the README says so.

### AWS free plan constraints

- Athena, S3, EC2, Glue, Lambda, EventBridge, CloudWatch, IAM and SNS are listed for the free plan under the "Sign up for AWS (new)" path. Availability must be confirmed in the account at creation.
- The free plan does not charge unless the account is upgraded.
- Credits are 100 USD, plus up to 100 USD for completing activities.
- The plan ends after six months or when credits run out, whichever comes first. The account then closes, and AWS keeps the data for 90 days.
- Code therefore lives on GitHub and the dashboard's Parquet file lives outside AWS. No upgrade is assumed.

## 5. Data model

### dbt layers

| Layer | Purpose | Examples |
|---|---|---|
| staging | Rename columns, cast types, normalize tax codes (`RO 123` and `123.0` become `123`) | `stg_contracts`, `stg_notices` |
| intermediate | Deduplicate across files, link contracts to notices, resolve suppliers | `int_awards_unified`, `int_suppliers_resolved` |
| marts | Final tables for the dashboard and the model | below |

### Marts

**Facts**

- `fct_awards`: one row per award notice, lot, contract number, winner and value, after deduplication. Lot is `NULL` where files have none. Holds the published value, the contract type, how the contract was concluded, and the first and latest file it appeared in.
- `fct_contract_competition`: one row per award notice and contract number. Holds the bid count, which is `NULL` where the source has none, and a single-offer flag.
- `fct_procedures`: one row per initiation notice, with lot-level notices from 2026 Q3 reduced to procedure level. Holds the estimated value and the procedure details.

**Dimensions**

- `dim_authority`: by tax code, with type and county taken from notices and contract files, using the most recent known value.
- `dim_supplier`: by normalized tax code, with the most recent name.
- `dim_cpv`: CPV code and its top-level group (first two digits).
- `dim_date`: standard calendar.

**Dashboard tables**

- `mart_authority_competition`: competition by authority and year, for years with bid counts.
- `mart_contracted_value`: contracted value by year and kind of contract, with the suspect values excluded.
- `mart_supplier_concentration`: market share of the top suppliers by county, CPV group and year, on real contracts from 2023.

### Rules that keep the numbers correct

1. **Only a contract's latest file counts.** For each award notice, lot, contract number and winner, rows come from the latest file that holds them, because republished contracts can change value. Rows in that file with different values stay, because older files have no lots and one contract number can cover several items. The repeated 2019 Q2 file is excluded.
2. **Contracted value has a strict definition.** It is the sum of `Fara acord cadru` and `Cu acord cadru subsecvent` contracts, by contract year from 2023. Joint winners repeat a value, so each contract counts once. Earlier years get no spending total, because most of their files cannot separate ceilings from real contracts.
3. **Framework ceilings get no totals.** `Cu acord cadru` values are ceilings that repeat for each winner, so only counts and medians are published.
4. **Suspect values stay out of totals.** A value is suspect if it is zero or negative, above 10 billion RON, or more than 10 times the procedure's estimate. It stays in `fct_awards`, flagged, and the dashboard shows how many were excluded.
5. **One winner does not mean one bidder.** Winner count says nothing about offers and must not stand in for the bid count.
6. **Gaps stay gaps.** Bid count is `NULL`, never 0, where the source has none. The dashboard shows clearly where the data stops, including 2019 Q2 and 2022 Q1.
7. **Only RON for estimated values.** Other currencies stay `NULL`.
8. **County comes from `dim_authority`.** Notices stop carrying county after 2024 Q3, and contract files have none. Authorities with no earlier notice, about 5% in 2025–2026, stay `NULL`.
9. **No dimension history.** Only the most recent values are kept.

## 6. ML model

### Target

The probability that a contract receives exactly one offer, using only what is known when the notice is published.

- **Unit:** the award notice plus contract number. The bid count is stable at this level, and varies in only 1.6% of units.
- **Disagreements:** the maximum bid count applies, so a unit is single-offer only if every row says so.

Procedures without real competition, such as negotiation without a participation notice, are excluded because a single offer is normal there. In the data, 49.7% of those units have one offer, and 98.8% for accelerated negotiation.

### Features

- **Used:** CPV group, contract type, procedure type, estimated value, month, authority type and authority history.
- **Authority type** comes from `dim_authority`, because notices do not carry it.
- **Authority history** uses only data from before each procedure.
- **Never used:** final value, winner, contract date, or any other field that appears after award.
- **Not available:** the award criterion, because notices after 2022 do not carry it.

### Training and evaluation

| Step | Period | Role |
|---|---|---|
| Training | 2016–2020 | Fit models and tune parameters |
| Validation | 2021 | Choose the final variant |
| Final fit | 2016–2021 | Used for the test run and for later scores |
| Test | 2022 Q2–Q4 | Run once, at the end |

- **Time split:** each contract belongs to the year its procedure first appeared, so neither a republished contract nor a later contract of the same framework can reach both training and test.
- **Variants compared:** a mean rate by CPV group and procedure type, logistic regression, and LightGBM. On the 2021 validation data, LightGBM is chosen only if its PR-AUC is at least 0.02 higher than logistic regression and its calibration is no worse, with differences under 0.5 points treated as noise. The same rule applies between logistic regression and the mean rate.
- **Metrics:** PR-AUC, because single-offer cases are the minority, and calibration, because a predicted 30% should mean about 30% in reality.
- **No fixed performance threshold.** If the model does not beat the simple mean, that result is published and the simple variant stays.
- **No periodic retraining.** No new labels exist after 2022, so the model is trained once and versioned. Monthly runs only score and monitor.

### Outputs

- **2021–2022:** the difference between actual and expected single-offer rates by authority, using only predictions on contracts the model had not seen. Only authorities with at least 30 contracts appear, each with a confidence interval, and only through a lookup with no ranking.
- **From 2023:** estimated risk only, visibly marked as unvalidated. Scores are computed from initiation notices, before award.
- **Monitoring:** accuracy cannot be measured after 2022. Input drift is tracked with PSI, per procedure, because notices are procedures and contract-level training data would look like drift. The dashboard shows which features exceed 0.25, with the 2022 test data as a reference.

### Fallback

Training uses contract files, while scoring from 2023 uses initiation notices. On 106,122 joined procedures from the labelled years, estimated values and CPV codes match almost completely, but this cannot be tested after 2022, because contract files no longer carry the estimate. If PSI shows a lasting break, the feature set shrinks. If that is not enough, scores after 2022 are dropped and the model stays historical only.

### Public wording

There is no "suspicious authorities" ranking. The dashboard speaks of deviations from expectation and states that a high score does not mean wrongdoing. A single offer can have normal explanations, such as a highly specialized market.

## 7. Error handling

The dashboard receives new data only if every check has passed. Otherwise it stays on the last good version.

| Stage | Problem | Response |
|---|---|---|
| Ingestion | Portal does not respond | Retries with increasing delays, then a visible failure in Airflow |
| Ingestion | File extension does not match content | File type is detected from content, not from its name |
| Ingestion | File known to be wrong | A list in code excludes it or replaces it with a correct version, with the reason recorded |
| Ingestion | File republished with new content | New hash, so that quarter is replaced and the change is logged |
| Standardization | Unknown column | File is quarantined with an alert, and other files continue |
| Standardization | Unreadable, malformed or junk rows | Rows go to a rejects table with a reason. Above 1% rejected rows, the file fails |
| Standardization | File dates fall outside its period | Warning for review. Files before 2018 Q2 legitimately hold some earlier dates |
| dbt | Test failure | Publishing stops |
| Model | PSI exceeds 0.25 on any feature | Scores are published with a warning |

The 1% threshold is a starting value. In the validated data, no file came near it: 31 rows were rejected and 9 were malformed across all files.

## 8. Cost controls

- **EC2:** the last Airflow task stops the instance even when the run fails, and a separate rule force-stops it after 4 hours.
- **Budget alerts:** thresholds at 50% and 80% of credits, sent by email through SNS, because running out of credits closes the account.
- **Athena:** a workgroup limit on bytes scanned per query blocks oversized queries.
- **Query price:** Athena costs 5 USD per TB scanned, with no Athena-specific free tier listed on its pricing page. Parquet partitioning keeps scans small.

## 9. Testing

**In GitHub Actions, with no AWS cost**

- Parsers: one test per format generation, on small samples from real files.
- Logic: tax code normalization, date inference, hashing and file type detection.
- Leakage: authority history uses no future data, no post-award field reaches the model, and no unit appears on both sides of the time split.
- Static checks: Airflow DAGs load, the dbt project compiles and `terraform validate` passes.

**On data, in every pipeline run**

- dbt: unique keys, required fields and relationships between tables.
- Reconciliation: rows in raw files must be found in final tables, in the rejects table or among removed republications.
- Domain rules: bid count is `NULL` for 2022 Q1 and from 2023 onwards, and framework ceilings stay out of contracted value.

**Once, before the full load**

- End-to-end run on one quarter, in a separate S3 prefix, to avoid wasting credits.

## 10. Build order

1. **Data validation:** done. See the [report](../../data-validation.md).
2. **Complete warehouse:** standardization and dbt run locally on DuckDB. Still to do: moving dbt to Athena, Airflow and Terraform.
3. **Public dashboard:** done, at [seap-lens.streamlit.app](https://seap-lens.streamlit.app/), on a 548 KB extract.
4. **ML model:** done. See the [results](../../model-results.md).
5. **Polish:** README, diagram, Airflow screenshots and main findings.

## 11. Open questions

| Question | Stage | If the answer is bad |
|---|---|---|
| Which EC2 instance type is available on the free plan, and at what hourly cost? | 2 | Reduce instance size or the time the instance runs |
| Does dbt-athena support the incremental loads needed, with Iceberg? | 2 | Rebuild tables instead of loading incrementally |
| Can contracted value be compared with an official figure? No official total was found on 2026-10-30 | 3, before publishing | The dashboard keeps marking totals as unverified estimates |

## 12. Sources

- [data.gov.ro procurement datasets](https://data.gov.ro/api/3/action/package_search?q=achizitii+publice&rows=30)
- [Services on the AWS free plan](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html)
- [AWS account plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
- [Athena pricing](https://aws.amazon.com/athena/pricing/)
