"""Builds the dbt documentation site on the sample data, so it shows real column types.

    python -m scripts.build_docs OUTPUT_DIR

Writes OUTPUT_DIR/index.html, a single static page with no AWS access needed.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from src.sample_data import write_sample_data

DBT_DIR = Path(__file__).resolve().parent.parent / "dbt"


def main() -> None:
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    dbt = shutil.which("dbt", path=str(Path(sys.executable).parent)) or "dbt"
    with tempfile.TemporaryDirectory() as work:
        root = Path(work)
        write_sample_data(root)
        environment = {**os.environ, "SEAP_DATA_DIR": str(root), "SEAP_DB": str(root / "warehouse.duckdb")}
        paths = ["--profiles-dir", ".", "--target-path", str(root / "target"), "--log-path", str(root / "logs")]
        for command in (["build"], ["docs", "generate", "--static"]):
            subprocess.run([dbt, *command, *paths], cwd=DBT_DIR, env=environment, check=True)
        shutil.copy(root / "target" / "static_index.html", output / "index.html")
    print(f"Wrote {output / 'index.html'}")


if __name__ == "__main__":
    main()
