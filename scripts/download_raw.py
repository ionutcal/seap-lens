"""Downloads the in-scope SEAP files into data/raw and records them in a manifest."""

import csv
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from src.catalog import Resource, fetch_catalog

RAW_DIR = Path("data/raw")
MANIFEST = RAW_DIR / "manifest.csv"
ATTEMPTS = 3


def target_path(resource: Resource) -> Path:
    return RAW_DIR / resource.kind / f"{resource.year}_{resource.period}_{resource.filename}"


def download(resource: Resource) -> dict:
    path = target_path(resource)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(path.suffix + ".part")
        for attempt in range(1, ATTEMPTS + 1):
            try:
                with requests.get(resource.url, stream=True, timeout=120) as response:
                    response.raise_for_status()
                    with partial.open("wb") as handle:
                        for chunk in response.iter_content(1024 * 1024):
                            handle.write(chunk)
                partial.replace(path)
                break
            except requests.RequestException as error:
                print(f"attempt {attempt} failed for {resource.filename}: {error}", flush=True)
                if attempt == ATTEMPTS:
                    return {**row(resource, path), "status": f"failed: {error}"}
    return {**row(resource, path), "status": "ok"}


def row(resource: Resource, path: Path) -> dict:
    exists = path.exists()
    return {
        "year": resource.year,
        "kind": resource.kind,
        "period": resource.period,
        "name": resource.name,
        "url": resource.url,
        "path": str(path),
        "bytes": path.stat().st_size if exists else "",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if exists else "",
    }


def main() -> None:
    resources = fetch_catalog()
    print(f"{len(resources)} files in scope", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = []
        for result in pool.map(download, resources):
            rows.append(result)
            print(result["path"], result["bytes"], result["status"], flush=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    failed = [r for r in rows if r["status"] != "ok"]
    total = sum(int(r["bytes"]) for r in rows if r["bytes"] != "")
    print(f"done: {len(rows) - len(failed)} ok, {len(failed)} failed, {total / 1e9:.2f} GB", flush=True)


if __name__ == "__main__":
    main()
