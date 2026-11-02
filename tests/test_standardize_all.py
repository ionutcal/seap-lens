import json

import scripts.standardize_all as run


def entry():
    return {"kind": "contracts", "year": "2023", "period": "Q1", "sha256": "abc"}


def prepare(tmp_path, monkeypatch, version):
    monkeypatch.setattr(run, "SUMMARY", tmp_path / "summary.jsonl")
    monkeypatch.setattr(run, "STANDARD_DIR", tmp_path)
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts" / "2023_Q1.parquet").write_text("x")
    (tmp_path / "summary.jsonl").write_text(json.dumps({"sha256": "abc", "version": version, "rejected_share": 0}) + "\n")


def test_unchanged_file_is_not_processed_again(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch, run.OUTPUT_VERSION)
    assert run._unchanged(entry()) is not None


def test_file_written_by_an_older_format_is_processed_again(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch, run.OUTPUT_VERSION - 1)
    assert run._unchanged(entry()) is None
