from scripts.download_raw import needs_download
from src.catalog import Resource


def resource(modified):
    return Resource(2024, "contracts", "Q1", "Contracte", "https://x/c.csv", modified)


def test_missing_file_is_downloaded(tmp_path):
    assert needs_download(resource("2024-01"), tmp_path / "c.csv", {})


def test_unchanged_file_is_not_downloaded_again(tmp_path):
    path = tmp_path / "c.csv"
    path.write_text("x")
    assert not needs_download(resource("2024-01"), path, {str(path): {"modified": "2024-01"}})


def test_republished_file_is_downloaded_again(tmp_path):
    path = tmp_path / "c.csv"
    path.write_text("x")
    assert needs_download(resource("2024-06"), path, {str(path): {"modified": "2024-01"}})


def test_file_from_before_dates_were_recorded_is_kept(tmp_path):
    path = tmp_path / "c.csv"
    path.write_text("x")
    assert not needs_download(resource("2024-06"), path, {str(path): {"path": str(path)}})
