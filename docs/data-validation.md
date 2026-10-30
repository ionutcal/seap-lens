# Data Validation Report

**Date:** 2026-10-30
**Scope:** all contract and initiation notice files from data.gov.ro, 2016 to 2026 Q3
**Reproduce:** `python -m scripts.download_raw`, `python -m scripts.standardize_all`, `dbt build` in `dbt/`, then `python -m scripts.warehouse_summary`

This report closes the data questions in section 11 of the [design spec](superpowers/specs/2026-10-30-seap-lens-design.md). An earlier version misread values with thousands commas, which distorted its missing-value and republication figures. Those figures are corrected here.

## Summary

- All files read with no errors, in 2.40 GB of raw files: 3,986,575 contract rows and 304,514 notice rows after removing 31 junk rows. Another 9 CSV rows were malformed.
- Bid counts run to the end of 2022, not 2021, apart from two gaps: 2019 Q2 and 2022 Q1.
- The bid count belongs to the contract within an award notice. There are 557,340 usable labels.
- The same contract rows are republished across files, and 7.7% of republished contracts change value. Deduplication brings 4.0 million rows down to 2.18 million awards.
- The first spec's rule for framework agreements was wrong, because it dropped real subsequent contracts.
- Value totals need an outlier rule. Framework ceilings dated 2024 sum to more than 20,000 billion RON.

## Answers to the open questions

| Question | Answer |
|---|---|
| Unique keys | Award notice, lot, contract number, winner and value is unique once republished rows are resolved, as tested by dbt |
| Meaning of the bid count | The contract within an award notice. It varies inside 41.6% of multi-row award notices, but only 1.6% of notice and contract number units |
| Old and new notice IDs | Numeric IDs give way to `CN` and `SCN` during 2018. No link between the two is needed, because each contract row carries its own notice ID |
| Bid count after 2021 | Present in 2022 Q2–Q4. Absent from 2022 Q1 and from 2023 onwards, including 2025 |
| County for older contracts | Contract files have no county, so it comes from notices through the authority's tax code. Only 0.12% of awards end up without one |
| Field alignment for scoring | Very good in the labelled years. On 106,122 joined procedures, estimated values match on 100% of comparable rows after rounding, and CPV codes on 99.99%. Alignment after 2022 cannot be tested this way, because contract files no longer carry the estimate |
| Malformed CSV rows | 9 in total, all in 2016 S1 |
| Full dataset size | 2.40 GB raw. Volume stays small enough for Athena |
| Licence | OGL-ROU-1.0 for 2016–2020 and CC BY 4.0 for 2021–2026. The source is attributed in the dashboard and the README |

Still open, because they are not data questions: the EC2 instance type and cost, Iceberg support in dbt-athena, and an official figure to compare contracted value with.

## Files that are wrong as published

| File | Problem | Handling |
|---|---|---|
| Contracts 2024 Q1, CSV | Truncated: 21,433 rows against 151,431 in the XLS | Excluded in `src/catalog.py` in favour of the XLS |
| Contracts 2019 Q2 | Same content as 2019 Q3, with dates from July to September | Excluded in `src/catalog.py`. Q2 2019 is missing |
| Notices 2017 Q1 | Holds dates from July to December 2015 | Kept, since the dates are valid. Q1 2017 notices are missing |

Comparing CSV and XLS versions found no other truncation. Row counts match for 2023 Q3, 2024 Q1 and 2024 Q2 notices and 2023 Q3 contracts, and differ by 2 rows for 2023 Q4 contracts. The XLS for 2024 Q2 contracts could not be read, so that CSV has no second source.

## Format drift

- **Columns:** 158 distinct contract names and 96 notice names map to one schema in `src/schema.py`. An unknown column raises an error.
- **Dates:** ISO, month first, day first and Excel serial numbers all occur, and the convention changes between files. `src/dates.py` infers it per file.
- **Numbers:** 2023 Q4 and 2024 Q2 write 417185 as `417,185`. On 732,157 pairs of rows republished in other files, reading the comma as a thousands separator gives the same value 96% of the time, and reading it as a decimal almost never does.
- **Encoding:** contracts in 2016 and 2023 Q4 are not UTF-8 and are read as Windows-1250.
- **Sheets:** spreadsheets split at 65,000 rows repeat the header on each sheet. 2023 Q1 has a title row above the header, and 2026 Q3 has a legend sheet.
- **File type:** 2026 Q2 files are `.ods` although the portal declares them as `.xlsx`.
- **Tax codes:** 2026 Q3 stores them as numbers, such as `4453144.0`. `normalize_cui` handles this.
- **Grain:** 2026 Q3 notices move to one row per lot. `fct_procedures` reduces them to one row per notice.
- **Junk rows:** 31 rows, including repeated headers and SQL footers such as `(9 row(s) affected)`. They go to `data/rejects` with a reason.

## Republication

Of 2,107,303 contracts (award notice, lot, contract number, winner), 801,209 appear in more than one file. In 2023–2026, 53–64% of each year's rows had already appeared in an earlier file.

- **Values change:** 61,660 republished contracts, or 7.7%, have more than one value. Only the latest file counts, so a contract's old value is not added to its new one.
- **Rows within that file can still differ by value:** older files have no lots, so one contract number can cover several items.
- **Years come from the contract date.** A contract republished years later must not move to the later year.
- **Time split:** a contract published in both training and test would leak the answer, so the split uses its first appearance.

## Bid count labels

The usable unit is the award notice plus contract number. Where rows disagree, the maximum applies, so a contract is single-offer only if every row says so.

Each contract is counted in the year it first appeared, without procedures that have no real competition.

| Year | Usable labels | Single-offer share |
|---|---|---|
| 2016 | 40,589 | 21.6% |
| 2017 | 31,725 | 24.3% |
| 2018 | 28,568 | 36.2% |
| 2019, without Q2 | 40,534 | 35.3% |
| 2020 | 82,607 | 28.5% |
| 2021 | 210,634 | 25.3% |
| 2022 Q2–Q4 | 122,683 | 25.7% |

That gives 223,023 for training, 210,634 for validation and 122,683 for the test.

## Contract values

From 2022 Q1 and again from 2023, a column shows how each contract was concluded.

| Concluded through | Awards, all years | Median (RON) | Missing values | Meaning |
|---|---|---|---|---|
| `Cu acord cadru` | 533,106 | 180,192 | 14.4% | Framework ceilings, not spending |
| `Cu acord cadru subsecvent` | 655,795 | 13,847 | 0% | Real contracts under a framework |
| `Fara acord cadru` | 183,666 | 289,034 | 0% | Standalone contracts |
| Not published | 804,763 | 24,840 | 6.0% | Files without the column |

Contracted value by contract year, counting joint winners once and leaving out suspect values:

| Year | Standalone (billion RON) | Subsequent (billion RON) | Total (billion RON) |
|---|---|---|---|
| 2023 | 131.3 | 31.7 | 163.0 |
| 2024 | 133.4 | 34.9 | 168.3 |
| 2025 | 159.0 | 54.5 | 213.5 |
| 2026, to Q3 | 89.0 | 31.7 | 120.7 |

A search on 2026-10-30 found no official national total to compare these with, so they are published as unverified estimates.

### Outlier rule

A value is suspect if it is zero or negative, above 10 billion RON, or more than 10 times the procedure's estimate. Suspect values stay in `fct_awards`, flagged, and stay out of totals. The dashboard shows how many were excluded.

Without the rule, one 2025 contract would add 125.9 billion RON, against an estimate of about 0.8 million RON. It removes 1,187 of the contracts counted above, most of them zero or negative values.

The rule does not check every value, and both thresholds are judgement calls. A real contract above 10 billion RON would be excluded, though none looks real at present: the largest value left among real contracts is 9.06 billion RON.

Ceilings get no totals at all. They repeat for each winner, and those dated 2024 sum to 20,505 billion RON, with one at 177.9 billion RON.

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

The award criterion stays out of the model, because it cannot be scored after 2022.
