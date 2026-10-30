# Data Validation Report

**Date:** 2026-10-30
**Scope:** all contract and initiation notice files from data.gov.ro, 2016 to 2026 Q3
**Reproduce:** `python -m scripts.download_raw`, then `python -m scripts.profile_raw`, then `python -m scripts.validate_data`

This report closes the data questions in section 11 of the [design spec](superpowers/specs/2026-10-30-seap-lens-design.md). It replaces the sample-based findings in section 2 of the spec wherever they differ.

## Summary

- 81 files were read with no errors: 4,004,161 contract rows and 304,519 notice rows, in 2.43 GB of raw files.
- Bid counts run to the end of 2022, not 2021, apart from two gaps: 2019 Q2 and 2022 Q1.
- The bid count belongs to the contract within an award notice. About 816,000 contract-level labels are available before removing republished units.
- The same contract rows are republished across files: 4.0 million rows hold 2.4 million distinct keys.
- The spec's rule for framework agreements is wrong, because it would drop real subsequent contracts.
- Contract and notice fields align very well for scoring, but the award criterion is not available in notices after 2022.
- Value totals cannot be trusted without outlier handling. Framework ceilings in 2026 sum to more than 20,000 billion RON.

## Answers to the open questions

| Question | Answer |
|---|---|
| Unique keys | Award notice, lot, contract number, winner and value is nearly unique within a file. Across files it is not, because rows are republished |
| Meaning of the bid count | The contract within an award notice. It varies inside 41.6% of multi-row award notices, but only 1.6% of notice and contract number units |
| Old and new notice IDs | Numeric IDs give way to `CN` and `SCN` during 2018. No link between the two is needed, because each contract row carries its own notice ID |
| Bid count after 2021 | Present in 2022 Q2–Q4. Absent from 2022 Q1 and from 2023 onwards, including 2025 |
| County for older contracts | Contract files have no county, so it comes from notices through the authority's tax code. This covers 94–99.9% of authorities per year from 2016, and 94–95% in 2025–2026 |
| Field alignment for scoring | Very good in the labelled years. On 106,122 joined procedures, estimated values match on 100% of comparable rows after rounding, and CPV codes on 99.99%. Alignment after 2022 cannot be tested this way, because contract files no longer carry the estimate |
| Full dataset size | 2.43 GB raw. Volume stays small enough for Athena |
| Licence | CC BY 4.0 on the 2025 dataset, the only one checked. Attribution is required |

Still open, because they are not data questions: the EC2 instance type and cost, Iceberg support in dbt-athena, and the size of the dashboard's Parquet file.

## Files that are wrong as published

| File | Problem | Handling |
|---|---|---|
| Contracts 2024 Q1, CSV | Truncated: 21,433 rows against 151,431 in the XLS | Excluded in `src/catalog.py` in favour of the XLS |
| Contracts 2019 Q2 | Same content as 2019 Q3, with dates from July to September | Q2 2019 is missing. The repeated file must be dropped |
| Notices 2017 Q1 | Holds dates from July to December 2015 | Q1 2017 notices are missing |

Comparing CSV and XLS versions found no other truncation. Row counts match for 2023 Q3, 2024 Q1 and 2024 Q2 notices and 2023 Q3 contracts, and differ by 2 rows for 2023 Q4 contracts. The XLS for 2024 Q2 contracts could not be read, so that CSV has no second source. CSV rows that pandas skips as malformed have not been counted yet; the rejects table in stage 2 must count them.

## Format drift

- **Columns:** 158 distinct contract names and 96 notice names map to one schema in `src/schema.py`. An unknown column raises an error.
- **Dates:** ISO, month first, day first and Excel serial numbers all occur, and the convention changes between files. `src/dates.py` infers it per file. Every date column in the files parses, apart from under 0.1% of rows in a few older files.
- **Encoding:** contracts in 2016 and 2023 Q4 are not UTF-8 and are read as Windows-1250.
- **Sheets:** spreadsheets split at 65,000 rows repeat the header on each sheet. 2023 Q1 has a title row above the header, and 2026 Q3 has a legend sheet.
- **File type:** 2026 Q2 files are `.ods` although the portal declares them as `.xlsx`.
- **Tax codes:** 2026 Q3 stores them as numbers, such as `4453144.0`. `normalize_cui` handles this.
- **Grain:** 2026 Q3 notices move to one row per lot, with 25,183 repeated notice IDs. Procedure-level use must deduplicate them.
- **Junk rows:** very few. 11 contract rows have an unknown contract type, 19 have no award notice, and 5 notices have no valid ID, including SQL footers such as `(9 row(s) affected)`.

## Republication

The same key (award notice, lot, contract number, winner, value) appears in more than one file for 800,825 of 2,409,652 distinct keys. Only 11,489 rows are repeats within a single file, so this happens between files. In 2023–2026, 41–63% of each year's rows had already appeared in an earlier file.

This matters in two ways:

- Every total and count must deduplicate across files, keeping the latest publication.
- A contract published in both the training and test periods would leak the answer. The time split must use the first time a unit appears.

## Bid count labels

The usable unit is the award notice plus contract number. Where a unit's rows disagree (12,991 of 830,146 units), the maximum applies, so a unit counts as single-offer only if every row says so.

Unit counts below are per file. They include the repeated 2019 file and still contain units republished between files.

| Period | Units | Single-offer share |
|---|---|---|
| 2016 | 46,904 | 23–27% |
| 2017 | 37,878 | 25–37% |
| 2018 | 29,994 | 32–41% |
| 2019, without Q2 | 40,537 | 33–37% |
| 2020 | 83,339 | 27–30% |
| 2021 | 320,239 | 24–25% |
| 2022 Q2–Q4 | 257,281 | 24–27% |

Single-offer share by procedure supports the planned exclusions: 49.7% for negotiation without a participation notice and 98.8% for accelerated negotiation, against 23.8% for open tenders and 34.2% for simplified procedures.

## Contract values

From 2022 Q1 and again from 2023, a column shows how each contract was concluded. Figures for 2025, after deduplication:

| Concluded through | Rows | Median (RON) | Sum (billion RON) | Meaning |
|---|---|---|---|---|
| `Cu acord cadru` | 126,261 | 203,729 | 889.6 | Framework ceilings, not spending |
| `Cu acord cadru subsecvent` | 142,040 | 17,000 | 101.2 | Real contracts under a framework |
| `Fara acord cadru` | 49,382 | 384,962 | 721.3 | Standalone contracts |

Three limits follow:

- **The column is missing from 2016–2021 and from 2022 Q2–Q4.** Those files cannot separate ceilings from real contracts, so spending series can only start in 2023, or use 2022 Q1 as a partial point.
- **Values are often missing in 2023–2024:** 30–31% of rows, against 1–3% in 2025–2026.
- **Outliers are severe.** One standalone contract in 2025 shows 125.9 billion RON. Framework ceilings in 2026 sum to 20,290 billion RON, with one at 177.9 billion. These look like entry errors, but that has not been confirmed. No total can be published without an outlier rule.

## Feature availability for scoring

| Feature | Contract files | Notices after 2022 |
|---|---|---|
| CPV code, contract type, procedure type | Yes | Yes |
| Estimated value | Until 2022 | Yes |
| Publication date | Yes | Yes |
| Authority tax code | Yes | Yes |
| County | No | Until 2024 Q3, then through `dim_authority` |
| Authority type | Until 2024 Q3 | No, only through `dim_authority` |
| Award criterion | Yes | **No** |

The award criterion must leave the model, because it cannot be scored after 2022.

## Proposed spec changes

All of these were applied to the spec on 2026-10-30.

1. **Time split:** train on 2016–2020, validate on 2021, test on 2022 Q2–Q4, and do the final fit on 2016–2021. Scores from 2023 onwards are unvalidated. The test becomes more recent, and it is 2022 data the model has not seen.
2. **Label unit:** the award notice plus contract number, taking the maximum bid count.
3. **Contracted value:** `Fara acord cadru` plus `Cu acord cadru subsecvent`, from 2023. Ceilings stay separate, and earlier years do not get a spending total.
4. **Deduplication:** across files, keeping the latest publication. The model's time split uses first appearance.
5. **Outlier rule:** required before any value total is published.
6. **Features:** drop the award criterion.
7. **County:** always from `dim_authority`, built from notices.
8. **Spec section 2:** replace the sample findings with this report.
