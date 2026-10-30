# SEAP Lens: Design Spec

**Date:** 2026-10-30
**Status:** Awaiting review
**Repository name:** `seap-lens`

## 1. Purpose

SEAP Lens is a portfolio project that turns Romanian public procurement data from SEAP/SICAP into a cloud data warehouse, a public dashboard and one integrated ML model.

It exists to close specific gaps on George Ionuț Călin's CV: cloud (AWS), orchestration (Airflow), dbt, dimensional modelling, infrastructure as code (Terraform) and applied ML in a data system. The assumed target is a Data Engineer or hybrid data role.

SEAP Lens is an independent project with no official link to SEAP, SICAP or any Romanian public authority. The README and the dashboard must both say so.

### Definition of done

- The dashboard is public and works with no AWS resources running.
- The pipeline can be rebuilt from the repository, with documented steps.
- CI passes, and dbt tests pass on the full dataset.
- The model's 2021 test result is published whatever it turns out to be, next to the simple baseline.
- The README states the limits openly: missing bid counts after 2021, unvalidated scores from 2022 onwards, and the choice of Airflow for quarterly data.

### Success test

A recruiter can open the dashboard and understand the findings within a few minutes. An engineer can find orchestration, tests and reproducible infrastructure in the repository.

## 2. What the data sample showed

These findings come from samples checked on 2026-10-30. The full dataset has not been profiled.

**Source:** yearly "Achiziții publice" datasets from the Autoritatea pentru Digitalizarea României on data.gov.ro, listed through its CKAN API.

### Bid count availability

| Period | Bid count field | Evidence |
|---|---|---|
| 2016 | Present (`NumarOfertePrimite`) | Header and content, 2016 S1: 0% missing |
| 2017–2018 | Present (`NumarOfertePrimite`) | Headers only, T1 of each year |
| 2019 | Present (`NUMAR_OFERTE`) | Header only, T1 |
| 2020 | Present (`NUMAR_OFERTE`) | Header and content, T1: 0.1% missing |
| 2021 | Present (`NUMAR_OFERTE`) | T1 content: 0% missing; T4 header |
| 2022, 2023, 2024, 2026 | Absent | 2022 T1, 2023 T3–T4, 2024 T1, 2026 T2 |
| 2025 | Not checked | |

The share of contract rows with exactly one offer was 16.7% in 2016 S1, 25.3% in 2020 T1 and 21.1% in 2021 T1. These are row-level figures, not procedure-level ones.

### Format and schema drift

- Separators vary between `^`, `|` and `,`. The 2022 T1 file also uses `|` as a quote character.
- Some 2026 files are `.ods` although the portal declares them as `.xlsx`.
- Column names change between quarters: `CUI_AC` in 2023 T3 becomes `CUI autoritate contractanta` in 2023 T4.
- The 2026 T2 contract file has 21 columns, against 27 in 2023 T3. It no longer has authority type, among others.
- Lot numbers (`NUMAR_LOT`) are absent from the 2016, 2019, 2020 and 2021 files checked.
- Notice identifiers are numeric in 2016 and look like `CN1051257` in 2023.
- The 2016 S1 file is not UTF-8. Its bytes point to a Windows-1252 style encoding (for example `0x96` for a dash), while the 2023 files are UTF-8. The parser must set the encoding per generation.

### Data quality

- Supplier tax codes appear as `RO 123`, `RO123` and `123`. In 2023 T3, 405 codes have more than one company name.
- Contract value is missing on 14.2% of rows in 2023 T3 and 1.1% in 2026 T2.
- In 2023 T3, 92.3% of contract rows belong to framework agreements. Raw contract value sums to 544.4 billion RON and falls to 224.7 billion after removing repeats on notice, lot, contract number and value. Even the lower figure is not real spending, because it still includes framework ceilings.
- All 1,072 initiation notices marked `Atribuita` in 2023 T3 match contracts from T3–T4, so the join works for awarded procedures.
- 5,921 of 8,086 initiation notices in 2023 T3 are `In desfasurare`. The field looks like a status at export time, so it is not usable as an outcome.
- About 1% of estimated values in 2023 T3 initiation notices are in a currency other than RON.

### Volume

The 2023 T3 contract file is about 100 MB. Total volume has not been measured, but nothing so far justifies distributed processing.

## 3. Scope

**In scope**

- Contract files and initiation notices, from 2016 to the present.
- A warehouse with tested dimensional marts.
- A public dashboard.
- One ML model that predicts single-offer procedures.

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
| Standardization | One parser per format generation, producing one schema with validation |
| dbt on Athena | Cleans data, resolves suppliers by tax code, and builds marts |
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
| staging | Rename columns, cast types, normalize tax codes (`RO 123` becomes `123`) | `stg_contracts`, `stg_notices` |
| intermediate | Unify format generations, link contracts to notices, remove repeats | `int_awards_unified`, `int_suppliers_resolved` |
| marts | Final tables for the dashboard and the model | below |

### Marts

**Facts**

- `fct_awards`: one row per award notice, lot, contract and winner. Holds the published value, the contract type and a framework flag.
- `fct_procedures`: one row per procedure. Holds the estimated value, the winner count and the bid count, which is `NULL` after 2021.

**Dimensions**

- `dim_authority`: by tax code, with type and county where available.
- `dim_supplier`: by normalized tax code, with the most recent name.
- `dim_cpv`: CPV code and its top-level group (first two digits).
- `dim_date`: standard calendar.

**Dashboard tables**

- `mart_authority_competition`: competition by authority and year.
- `mart_supplier_concentration`: market share of the top suppliers by county and CPV group.

### Rules that keep the numbers correct

1. **Values are never summed blindly.** Framework agreements are reported separately, as ceilings. "Contracted value" covers only rows that are not framework agreements.
2. **One winner does not mean one bidder.** Winner count exists after 2021 but says nothing about offers, and it must not stand in for the bid count.
3. **Gaps stay gaps.** Bid count after 2021 is `NULL`, never 0, and the dashboard shows clearly where the data stops.
4. **Only RON for estimated values.** Other currencies stay `NULL`.
5. **No dimension history.** Only the most recent supplier name is kept.

## 6. ML model

### Target

The probability that a procedure receives exactly one offer, using only what is known when the notice is published. Whether the unit is the contract or the procedure depends on validation step 1 in section 10.

Procedures without real competition, such as negotiation without a participation notice, are excluded because a single offer is normal there.

### Features

- **Used:** CPV group, contract type, procedure type, estimated value, award criterion, month and authority history.
- **Authority history** uses only data from before each procedure.
- **Never used:** final value, winner, contract date or any other field that appears after award.
- **Availability rule:** a feature must exist across all periods. Authority type, for example, is missing from the 2026 T2 file, so it can only come from `dim_authority` or it is dropped.

### Training and evaluation

| Step | Period | Role |
|---|---|---|
| Training | 2016–2019 | Fit models and tune parameters |
| Validation | 2020 | Choose the final variant |
| Final fit | 2016–2020 | The model that is kept |
| Test | 2021 | Run once, at the end |

- **Variants compared:** a mean rate by CPV group and procedure type, logistic regression, and LightGBM. On the 2020 validation data, LightGBM is chosen only if its PR-AUC is at least 0.02 higher than logistic regression and its calibration is no worse. The same rule applies between logistic regression and the mean rate.
- **Metrics:** PR-AUC, because single-offer cases are the minority, and calibration, because a predicted 30% should mean about 30% in reality.
- **No fixed performance threshold.** If the model does not beat the simple mean, that result is published and the simple variant stays.
- **No periodic retraining.** No new labels exist after 2021 in the files checked, so the model is trained once and versioned. Monthly runs only score and monitor.

### Outputs

- **Up to 2021:** the difference between actual and expected single-offer rates by authority. Only authorities with at least 30 procedures appear, each with a confidence interval.
- **From 2022:** estimated risk only, visibly marked as unvalidated. Scores are computed from initiation notices, before award.
- **Monitoring:** accuracy cannot be measured after 2021. Input drift against the training data is tracked with PSI, and the dashboard shows a warning when PSI exceeds 0.25 on any feature.

### Fallback

Training uses contract files, while scoring from 2022 uses initiation notices. If the fields do not mean the same thing in both, the feature set shrinks. If that is not enough, scores after 2021 are dropped and the model stays historical only.

### Public wording

There is no "suspicious authorities" ranking. The dashboard speaks of deviations from expectation and states that a high score does not mean wrongdoing. A single offer can have normal explanations, such as a highly specialized market.

## 7. Error handling

The dashboard receives new data only if every check has passed. Otherwise it stays on the last good version.

| Stage | Problem | Response |
|---|---|---|
| Ingestion | Portal does not respond | Retries with increasing delays, then a visible failure in Airflow |
| Ingestion | File extension does not match content | File type is detected from content, not from its name |
| Ingestion | File republished with new content | New hash, so that quarter is replaced and the change is logged |
| Standardization | Unknown column | File is quarantined with an alert, and other files continue |
| Standardization | Unreadable rows | Rows go to a rejects table with a reason. Above 1% rejected rows, the file fails |
| dbt | Test failure | Publishing stops |
| Model | PSI exceeds 0.25 on any feature | Scores are published with a warning |

The 1% threshold is a starting value, to be adjusted after seeing the full data. Older files may need a separate rule once their encoding is handled.

## 8. Cost controls

- **EC2:** the last Airflow task stops the instance even when the run fails, and a separate rule force-stops it after 4 hours.
- **Budget alerts:** thresholds at 50% and 80% of credits, sent by email through SNS, because running out of credits closes the account.
- **Athena:** a workgroup limit on bytes scanned per query blocks oversized queries.
- **Query price:** Athena costs 5 USD per TB scanned, with no Athena-specific free tier listed on its pricing page. Parquet partitioning keeps scans small.

## 9. Testing

**In GitHub Actions, with no AWS cost**

- Parsers: one test per format generation, on small samples from real files.
- Logic: tax code normalization, hashing and file type detection.
- Leakage: authority history uses no future data, and no post-award field reaches the model.
- Static checks: Airflow DAGs load, the dbt project compiles and `terraform validate` passes.

**On data, in every pipeline run**

- dbt: unique keys, required fields and relationships between tables.
- Reconciliation: rows in raw files must be found in final tables or in the rejects table.
- Domain rules: bid count is `NULL` after 2021, and framework values stay out of "contracted value".

**Once, before the full load**

- End-to-end run on one quarter, in a separate S3 prefix, to avoid wasting credits.

## 10. Build order

1. **Data validation:** settle the open data questions below before any modelling.
2. **Complete warehouse:** ingestion, standardization, dbt and Terraform.
3. **Public dashboard:** the first point where the project is complete enough to go on the CV.
4. **ML model:** training, evaluation and scores.
5. **Polish:** README, diagram, Airflow screenshots and main findings.

## 11. Open questions

These are unconfirmed and must be settled at the stage shown.

| Question | Stage | If the answer is bad |
|---|---|---|
| What are the unique keys in each format generation? | 1 | Keys differ by generation, with a generation column |
| Does the bid count apply to the contract, the lot or the procedure? | 1 | The model and `fct_procedures` use the contract as the unit |
| Can old numeric notice IDs link to `CN...` IDs, and when did the format change? | 1 | Each generation stays separate, with no cross-generation history |
| Is the bid count really absent from all files after 2021, including 2025? | 1 | If it is present anywhere, extend labels and revisit the test period |
| Can county be recovered for the older contract files? | 1 | County stays `NULL` there, and county views start later |
| Do contract and notice fields align for scoring? | 4 | Fallback in section 6 |
| Which EC2 instance type is available on the free plan, and at what hourly cost? | 2 | Reduce instance size or the time the instance runs |
| Does dbt-athena support the incremental loads needed, with Iceberg? | 2 | Rebuild tables instead of loading incrementally |
| Does the exported Parquet file fit on Streamlit Community Cloud? | 3 | Reduce the export to aggregates |
| What is the licence of the data.gov.ro datasets? | 1, before publishing | Adjust the attribution or what gets republished |
| How large is the full dataset? | 1 | Reconsider storage and query limits |

## 12. Sources

- [data.gov.ro procurement datasets](https://data.gov.ro/api/3/action/package_search?q=achizitii+publice&rows=30)
- [Services on the AWS free plan](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html)
- [AWS account plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
- [Athena pricing](https://aws.amazon.com/athena/pricing/)
