"""Reads every raw file, converts it to Parquet and records its structure."""

import csv
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from src.reader import detect_format, read_table

MANIFEST = Path("data/raw/manifest.csv")
INTERIM_DIR = Path("data/interim")
PROFILE = Path("data/profile.jsonl")


def profile(entry: dict) -> dict:
    path = Path(entry["path"])
    with path.open("rb") as handle:
        real_format = detect_format(handle.read(4096))
    result = {
        "year": int(entry["year"]),
        "kind": entry["kind"],
        "period": entry["period"],
        "path": str(path),
        "bytes": int(entry["bytes"]),
        "real_format": real_format,
    }
    try:
        frame = read_table(path)
    except Exception as error:  # A broken file must not stop the others from being profiled.
        return {**result, "error": repr(error)}
    target = INTERIM_DIR / entry["kind"] / f"{entry['year']}_{entry['period']}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.columns = [str(column) for column in frame.columns]
    attrs = dict(frame.attrs)
    frame.attrs = {}
    frame.to_parquet(target, index=False)
    return {
        **result,
        **attrs,
        "rows": len(frame),
        "columns": list(frame.columns),
        "null_share": frame.isna().mean().round(4).to_dict(),
        "parquet": str(target),
    }


def main() -> None:
    with MANIFEST.open() as handle:
        entries = list(csv.DictReader(handle))
    with ProcessPoolExecutor(max_workers=4) as pool, PROFILE.open("w") as out:
        for result in pool.map(profile, entries):
            out.write(json.dumps(result, ensure_ascii=False) + "\n")
            out.flush()
            print(
                result["year"], result["kind"], result["period"], result["real_format"],
                result.get("rows", result.get("error")), flush=True,
            )


if __name__ == "__main__":
    main()
