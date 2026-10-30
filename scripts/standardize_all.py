"""Standardizes every raw file into typed Parquet, plus rejected rows and a run summary."""

import csv
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from src.reader import read_table
from src.schema import standardize
from src.standardize import clean, save_parquet

MANIFEST = Path("data/raw/manifest.csv")
STANDARD_DIR = Path("data/standard")
REJECTS_DIR = Path("data/rejects")
SUMMARY = Path("data/standardize_summary.jsonl")
MAX_REJECTED_SHARE = 0.01


def _unchanged(entry: dict) -> dict | None:
    """Return the earlier summary of a file whose content hasn't changed since it was standardized."""
    if not SUMMARY.exists():
        return None
    target = STANDARD_DIR / entry["kind"] / f"{entry['year']}_{entry['period']}.parquet"
    with SUMMARY.open() as handle:
        for line in handle:
            earlier = json.loads(line)
            if earlier.get("sha256") == entry["sha256"] and target.exists():
                return earlier
    return None


def process(entry: dict) -> dict:
    kind, year, period = entry["kind"], int(entry["year"]), entry["period"]
    done = _unchanged(entry)
    if done:
        return done
    raw = read_table(Path(entry["path"]))
    malformed = raw.attrs.get("malformed", 0)
    rows, rejects = clean(standardize(raw, kind), kind)
    for frame in (rows, rejects):
        frame["file_year"], frame["file_period"], frame["source_sha256"] = year, period, entry["sha256"]
    name = f"{year}_{period}.parquet"
    for directory, frame in ((STANDARD_DIR, rows), (REJECTS_DIR, rejects)):
        save_parquet(frame, directory / kind / name)
    total = len(rows) + len(rejects) + malformed
    return {
        "kind": kind, "year": year, "period": period, "sha256": entry["sha256"], "rows": len(rows),
        "rejected": len(rejects), "malformed": malformed,
        "rejected_share": round((len(rejects) + malformed) / total, 5) if total else 0,
        "reasons": rejects.reject_reason.value_counts().to_dict() if len(rejects) else {},
    }


def main() -> None:
    with MANIFEST.open() as handle:
        entries = list(csv.DictReader(handle))
    failures = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(process, entries))
    with SUMMARY.open("w") as out:
        for result in results:
            out.write(json.dumps(result) + "\n")
            print(result, flush=True)
            if result["rejected_share"] > MAX_REJECTED_SHARE:
                failures.append(f"{result['kind']} {result['year']} {result['period']}")
    print(f"files above the {MAX_REJECTED_SHARE:.0%} rejected limit: {failures or 'none'}", flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
