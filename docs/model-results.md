# Model Results

**Date:** 2026-10-30
**Question:** can we predict which contracts will receive exactly one offer, using only what is known when the notice is published?
**Reproduce:** `python -m scripts.train_model validate`, `test` and `score`. The test refuses to run twice while its result exists.

**Answer: partly.** Logistic regression beats a simple average on data it had never seen and is well calibrated, but many single offers stay hard to foresee.

## Result on the 2022 test

The test covers 2022 Q2–Q4: 72,569 contracts from 20,003 procedures, with a base rate of 28.7%. The model was fit on 2016–2021 (483,765 contracts). It ran once, after the variant was chosen.

| | PR-AUC | PR-AUC, each procedure counted equally | Calibration error | Brier score |
|---|---|---|---|---|
| Logistic regression | **0.451** (95% interval 0.434–0.464) | 0.541 | 1.5 points | 0.189 |
| Mean rate by CPV group and procedure type | 0.405 | 0.507 | 1.9 points | 0.194 |

The interval resamples whole procedures, because contracts of one procedure move together.

## Choosing the variant on 2021

The variants were fit on 2016–2020 (232,746 contracts) and compared on 251,019 contracts from 2021.

| Variant | PR-AUC | PR-AUC, each procedure counted equally | Calibration error |
|---|---|---|---|
| Mean rate | 0.366 | 0.461 | 2.7 points |
| Logistic regression, chosen | 0.412 | 0.498 | 2.0 points |
| LightGBM | 0.420 | 0.524 | 2.5 points |

The rule was set in the spec before any results: a more complex variant must gain at least 0.02 PR-AUC without worse calibration. Logistic regression cleared it, and LightGBM did not, gaining 0.008. LightGBM does look better when each procedure counts equally, a measure the rule doesn't use.

## Preventing leakage

- **Features:** CPV group, contract type, procedure type, estimated value, publication month, authority type and authority history. Nothing that appears after award is used.
- **Authority history:** only awards published strictly before the notice.
- **Time split:** each contract takes the year its procedure first appeared. A framework can add contracts for years, with the same features and similar outcomes, so splitting it would leak the answer.
- **Exclusions:** procedures with no real competition, and 1,006 contracts with no publication date.

One small leak remains. Authority type comes from the most recent value known, not the value at publication. It rarely changes, so this should matter little, but it hasn't been measured.

## Scores from 2023

Bid counts stop after 2022, so these scores **can't be validated**. Authority history also stops at 2022.

Notices are procedures while the model was trained on contracts, so a score means the expected single-offer rate for a contract from that procedure.

| Year | Scored notices | Mean estimated risk | Features with PSI above 0.25 |
|---|---|---|---|
| 2023 | 29,947 | 37.1% | Procedure type |
| 2024 | 32,812 | 36.0% | Procedure type |
| 2025 | 25,911 | 36.8% | Procedure type |
| 2026, to Q3 | 17,190 | 36.5% | Procedure type, authority history size |

The 2022 test data shows a similar change against the training data, in procedure type and authority history size, and the model held up on it. So this isn't a new break, but that doesn't show accuracy held after 2022. Publication month is left out of the warning because a partial year always differs by month.

Measuring drift per contract first gave large values on most features. That was an artefact of comparing contracts with procedures, so drift is now measured per procedure.

## How to read the outputs

A difference from the expected rate is a statistical deviation, not a finding about an authority. The model doesn't know a market's real structure. For this reason the dashboard has a lookup, not a ranking, and compares only 2021–2022, where predictions come from contracts the model hadn't seen.
