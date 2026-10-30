"""Answers the spec's open data questions from the full dataset and writes them to JSON."""

import json
import re
from pathlib import Path

import pandas as pd
import requests

from src.dates import parse_dates
from src.schema import standardize

INTERIM_DIR = Path("data/interim")
OUTPUT = Path("data/validation.json")
QUARTER_MONTHS = {"Q1": (1, 3), "Q2": (4, 6), "Q3": (7, 9), "Q4": (10, 12), "S1": (1, 6), "S2": (7, 12), "Y": (1, 12)}


def load(kind: str) -> pd.DataFrame:
    frames = []
    for path in sorted((INTERIM_DIR / kind).glob("*.parquet")):
        year, period = path.stem.split("_")
        frame = standardize(pd.read_parquet(path), kind)
        frame["file_year"], frame["file_period"] = int(year), period
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def id_shape(value) -> str:
    if pd.isna(value):
        return "null"
    return re.sub(r"\d+", "9", str(value).strip())[:12]


def coverage(frame: pd.DataFrame, date_column: str) -> list[dict]:
    rows = []
    for (year, period), group in frame.groupby(["file_year", "file_period"]):
        current = parse_dates(group[date_column])
        first, last = QUARTER_MONTHS[period]
        inside = (current.dt.year == year) & current.dt.month.between(first, last)
        rows.append({
            "year": year, "period": period, "rows": len(group),
            "min": str(current.min())[:10], "max": str(current.max())[:10],
            "unparsed": round(current.isna().mean(), 4), "inside_period": round(inside.mean(), 4),
        })
    return rows


def repeated_files(frame: pd.DataFrame) -> list[list[str]]:
    hashes: dict[int, list[str]] = {}
    for (year, period), group in frame.groupby(["file_year", "file_period"]):
        content = group.drop(columns=["file_year", "file_period"])
        hashes.setdefault(int(pd.util.hash_pandas_object(content, index=False).sum()), []).append(f"{year}{period}")
    return [names for names in hashes.values() if len(names) > 1]


def bid_semantics(contracts: pd.DataFrame) -> dict:
    labelled = contracts[contracts.bid_count.notna()].copy()
    labelled["bids"] = pd.to_numeric(labelled.bid_count, errors="coerce")
    result = {"rows": len(labelled), "non_numeric": int(labelled.bids.isna().sum())}
    for name, keys in {
        "award_notice": ["award_notice_id"],
        "award_notice_contract": ["award_notice_id", "contract_number"],
        "participation_notice": ["participation_notice_id"],
    }.items():
        distinct = labelled.dropna(subset=keys).groupby(keys).bids.nunique()
        sizes = labelled.dropna(subset=keys).groupby(keys).size()
        result[name] = {
            "groups": len(distinct),
            "multi_row_groups": int((sizes > 1).sum()),
            "share_of_multi_row_with_varying_bids": round(float((distinct[sizes > 1] > 1).mean()), 4),
        }
    by_year = labelled.groupby("file_year").bids
    result["by_year"] = {
        int(year): {
            "rows": int(len(values)),
            "single_share_rows": round(float((values == 1).mean()), 4),
            "zero_share": round(float((values == 0).mean()), 4),
            "p99": float(values.quantile(0.99)),
        }
        for year, values in by_year
    }
    per_notice = labelled.dropna(subset=["award_notice_id"]).groupby(["file_year", "award_notice_id"]).bids.max()
    result["single_share_award_notices"] = {
        int(year): {"notices": int(len(values)), "single_share": round(float((values == 1).mean()), 4)}
        for year, values in per_notice.groupby(level=0)
    }
    return result


def key_quality(contracts: pd.DataFrame) -> dict:
    result = {}
    candidates = {
        "notice_contract_winner": ["award_notice_id", "contract_number", "winner_cui"],
        "notice_lot_contract_winner": ["award_notice_id", "lot_number", "contract_number", "winner_cui"],
        "notice_lot_contract_winner_value": ["award_notice_id", "lot_number", "contract_number", "winner_cui", "value_ron"],
    }
    for year, group in contracts.groupby("file_year"):
        current = {"rows": len(group), "exact_duplicates": int(group.drop(columns=["file_year", "file_period"]).duplicated().sum())}
        for name, keys in candidates.items():
            current[name] = int(group.duplicated(subset=keys).sum())
        result[int(year)] = current
    return result


def id_generations(frame: pd.DataFrame, column: str) -> dict:
    result = {}
    for year, group in frame.groupby("file_year"):
        result[int(year)] = group[column].map(id_shape).value_counts().head(4).to_dict()
    return result


def join_rates(contracts: pd.DataFrame, notices: pd.DataFrame) -> dict:
    known = set(notices.notice_id.dropna().astype(str).str.strip())
    result = {}
    for year, group in contracts.groupby("file_year"):
        ids = group.participation_notice_id.dropna().astype(str).str.strip().drop_duplicates()
        result[int(year)] = {"distinct_ids": len(ids), "matched": round(float(ids.isin(known).mean()), 4) if len(ids) else None}
    return result


def county_coverage(contracts: pd.DataFrame, notices: pd.DataFrame) -> dict:
    with_county = notices.dropna(subset=["county", "authority_cui"])
    known = set(with_county.authority_cui)
    result = {"notice_county_null_by_year": {int(y): round(float(g.county.isna().mean()), 4) for y, g in notices.groupby("file_year")}}
    result["contract_authorities_with_county"] = {
        int(year): round(float(pd.Series(group.authority_cui.dropna().unique()).isin(known).mean()), 4)
        for year, group in contracts.groupby("file_year")
    }
    return result


def scoring_alignment(contracts: pd.DataFrame, notices: pd.DataFrame) -> dict:
    vocabulary = lambda column: {
        "contracts": contracts[column].str.strip().value_counts().head(12).to_dict(),
        "notices": notices[column].str.strip().value_counts().head(12).to_dict(),
    }
    labelled = contracts[contracts.bid_count.notna()].drop_duplicates("participation_notice_id")
    merged = labelled.merge(notices.drop_duplicates("notice_id"), left_on="participation_notice_id", right_on="notice_id", suffixes=("_c", "_n"))
    left = pd.to_numeric(merged.estimated_value_c, errors="coerce")
    right = pd.to_numeric(merged.estimated_value_n, errors="coerce")
    usable = left.notna() & right.notna() & (right > 0)
    return {
        "procedure_type": vocabulary("procedure_type"),
        "contract_type": vocabulary("contract_type"),
        "criterion": vocabulary("criterion"),
        "labelled_join_rows": len(merged),
        "estimate_equal_share": round(float(((left - right).abs()[usable] <= 1).mean()), 4),
        "estimate_within_10pct_share": round(float((((left - right).abs() / right)[usable] <= 0.1).mean()), 4),
        "cpv_equal_share": round(float((merged.cpv_code_c.str.strip() == merged.cpv_code_n.str.strip()).mean()), 4),
        "estimate_null_contracts_by_year": {int(y): round(float(g.estimated_value.isna().mean()), 4) for y, g in contracts.groupby("file_year")},
    }


def value_quality(contracts: pd.DataFrame) -> dict:
    values = pd.to_numeric(contracts.value_ron, errors="coerce")
    result = {}
    for year, group in contracts.groupby("file_year"):
        current = values[group.index]
        result[int(year)] = {
            "null_share": round(float(current.isna().mean()), 4),
            "framework_share": round(float(group.agreement_type.fillna("").str.contains("cadru", case=False).mean()), 4),
            "negative_or_zero": int((current <= 0).sum()),
        }
    return result


def republication(contracts: pd.DataFrame) -> dict:
    """Measures how often the same contract row appears in more than one file."""
    keys = ["award_notice_id", "lot_number", "contract_number", "winner_cui", "value_ron"]
    tagged = contracts[keys + ["file_year", "file_period"]].copy()
    tagged["file"] = tagged.file_year.astype(str) + tagged.file_period
    files_per_key = tagged.groupby(keys, dropna=False).file.nunique()
    within_file = tagged.duplicated(keys + ["file"]).sum()
    notice_files = tagged.dropna(subset=["award_notice_id"]).groupby("award_notice_id").file.nunique()
    by_year = {}
    first_seen = tagged.drop_duplicates(keys)
    for year, group in tagged.groupby("file_year"):
        by_year[int(year)] = {
            "rows": len(group),
            "rows_new_globally": int((first_seen.file_year == year).sum()),
        }
    return {
        "rows": len(tagged),
        "distinct_keys": len(files_per_key),
        "keys_in_more_than_one_file": int((files_per_key > 1).sum()),
        "duplicate_rows_within_one_file": int(within_file),
        "award_notices": len(notice_files),
        "award_notices_in_more_than_one_file": int((notice_files > 1).sum()),
        "by_year": by_year,
    }


def contract_values(contracts: pd.DataFrame) -> dict:
    """Shows what each kind of row contributes, to decide which values count as spending."""
    keys = ["award_notice_id", "lot_number", "contract_number", "winner_cui", "value_ron"]
    frame = contracts.drop_duplicates(keys).copy()
    frame["value"] = pd.to_numeric(frame.value_ron, errors="coerce")
    frame["through"] = frame.concluded_through.fillna("(column missing)").str.strip()
    frame["agreement"] = frame.agreement_type.fillna("(column missing)").str.strip()
    result = {}
    for year, group in frame.groupby("file_year"):
        current = {}
        for (agreement, through), rows in group.groupby(["agreement", "through"]):
            if len(rows) < 50:
                continue
            current[f"{agreement} | {through}"] = {
                "rows": len(rows),
                "null_value": round(float(rows.value.isna().mean()), 4),
                "median": float(rows.value.median()) if rows.value.notna().any() else None,
                "sum_bn_ron": round(float(rows.value.sum()) / 1e9, 2),
                "max_bn_ron": round(float(rows.value.max()) / 1e9, 3) if rows.value.notna().any() else None,
            }
        result[int(year)] = current
    return result


def label_units(contracts: pd.DataFrame) -> dict:
    """Counts usable labels per year at the award notice and contract number level."""
    keys = ["award_notice_id", "contract_number"]
    labelled = contracts.dropna(subset=["bid_count", *keys]).copy()
    labelled["bids"] = pd.to_numeric(labelled.bid_count, errors="coerce")
    labelled["procedure"] = labelled.procedure_type.fillna("").str.strip()
    units = labelled.groupby(["file_year", "file_period", *keys]).agg(
        bids=("bids", "max"), varying=("bids", "nunique"), procedure=("procedure", "first")
    ).reset_index()
    by_quarter = (
        units.groupby(["file_year", "file_period"]).bids
        .agg(units="size", single_share=lambda values: round(float((values == 1).mean()), 4))
    )
    return {
        "units_total": len(units),
        "units_with_varying_bids": int((units.varying > 1).sum()),
        "by_file": {f"{year}{period}": row.to_dict() for (year, period), row in by_quarter.iterrows()},
        "single_share_by_procedure": (
            units.groupby("procedure").bids
            .agg(units="size", single_share=lambda values: round(float((values == 1).mean()), 4))
            .sort_values("units", ascending=False).head(10).to_dict("index")
        ),
    }


def junk_rows(contracts: pd.DataFrame, notices: pd.DataFrame) -> dict:
    known_types = {"Furnizare", "Servicii", "Lucrari"}
    misaligned = contracts.contract_type.notna() & ~contracts.contract_type.str.strip().isin(known_types)
    return {
        "contracts_with_unknown_contract_type": int(misaligned.sum()),
        "contracts_null_award_notice": int(contracts.award_notice_id.isna().sum()),
        "notices_without_valid_id": int((~notices.notice_id.fillna("").str.match(r"^([A-Z]+)?\d+$")).sum()),
        "notices_duplicate_id": int(notices.notice_id.duplicated().sum()),
        "notices_duplicate_id_2026q3": int(notices[(notices.file_year == 2026) & (notices.file_period == "Q3")].notice_id.duplicated().sum()),
    }


def licence() -> dict:
    response = requests.get("https://data.gov.ro/api/3/action/package_show", params={"id": "achizitii-publice-2025"}, timeout=60)
    result = response.json()["result"]
    return {key: result.get(key) for key in ("license_id", "license_title", "license_url")}


def main() -> None:
    contracts, notices = load("contracts"), load("notices")
    report = {
        "rows": {"contracts": len(contracts), "notices": len(notices)},
        "coverage_contracts": coverage(contracts, "award_notice_date"),
        "coverage_notices": coverage(notices, "notice_date"),
        "repeated_contract_files": repeated_files(contracts),
        "repeated_notice_files": repeated_files(notices),
        "bids": bid_semantics(contracts),
        "keys": key_quality(contracts),
        "award_id_shapes": id_generations(contracts, "award_notice_id"),
        "participation_id_shapes": id_generations(contracts, "participation_notice_id"),
        "notice_id_shapes": id_generations(notices, "notice_id"),
        "join_rates": join_rates(contracts, notices),
        "county": county_coverage(contracts, notices),
        "scoring": scoring_alignment(contracts, notices),
        "values": value_quality(contracts),
        "republication": republication(contracts),
        "contract_values": contract_values(contracts),
        "label_units": label_units(contracts),
        "junk": junk_rows(contracts, notices),
        "licence": licence(),
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    print(f"written to {OUTPUT}")


if __name__ == "__main__":
    main()
