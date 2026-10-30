"""Lists the SEAP contract and notice files published on data.gov.ro."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

import requests

API_URL = "https://data.gov.ro/api/3/action/package_show"
# Dataset slugs are not uniform: 2019 really is spelled "achiziti-".
DATASETS = {
    2016: "achizitii-publice-2016",
    2017: "achizitii-publice-2017",
    2018: "achizitii-publice-2018",
    2019: "achiziti-publice-2019",
    2020: "achizitii-publice-2020",
    2021: "achizitii-publice-2021",
    2022: "achizitii-publice-2022",
    2023: "achizitii-publice-2023",
    2024: "achizitii-publice-2024",
    2025: "achizitii-publice-2025",
    2026: "achizitii-publice-2026",
}
ROMAN_QUARTERS = {"i": 1, "ii": 2, "iii": 3, "iv": 4}
# Files outside the project's scope, some of which also mention contracts or notices.
EXCLUDED_TERMS = (
    "subsecvente",
    "modificare",
    "atribuire",
    "invitati",
    "directe",
    "notificari",
)
# Published files known to be wrong. See docs/data-validation.md.
BROKEN_FILES = {
    # 21,433 rows, while the XLS of the same period has 151,431.
    "datagov-raport-contracte-publicate-t-i-2024.csv",
    # A copy of 2019 Q3, with dates from July to September. No correct 2019 Q2 exists.
    "raport-t-2-2019.xls",
}


@dataclass(frozen=True)
class Resource:
    year: int
    kind: str  # "contracts" or "notices"
    period: str  # "Q1".."Q4", "S1", "S2" or "Y"
    name: str
    url: str
    # When the portal says the file last changed, so republished files can be fetched again.
    modified: str = ""

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[-1]


def _normalize(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def classify_kind(name: str) -> Optional[str]:
    """Return "contracts", "notices", or None for a file outside the project's scope."""
    normalized = _normalize(name)
    if any(term in normalized for term in EXCLUDED_TERMS):
        return None
    if "contract" in normalized:
        return "contracts"
    # "intiere" is a typo in the 2026 file names.
    if re.search(r"initiere|intiere|anunturi\s*participare", normalized):
        return "notices"
    return None


def parse_period(name: str) -> str:
    """Return the period in a file name, or "Y" when the file covers a whole year."""
    normalized = _normalize(name)
    semester = re.search(r"\bs([12])\b", normalized)
    if semester:
        return f"S{semester.group(1)}"
    quarter = re.search(r"\bt\s*(iv|iii|ii|i|[1-4])\b", normalized)
    if quarter:
        value = quarter.group(1)
        return f"Q{ROMAN_QUARTERS.get(value, value)}"
    return "Y"


def _format_rank(url: str) -> int:
    # Several periods are published twice. CSV is the fastest to read.
    return 0 if url.lower().endswith(".csv") else 1


def select_resources(year: int, raw_resources: list[dict]) -> list[Resource]:
    """Keep one file per kind and period from a dataset's resource list."""
    selected: dict[tuple[str, str], Resource] = {}
    for raw in raw_resources:
        kind = classify_kind(raw["name"])
        if kind is None or raw["url"].rsplit("/", 1)[-1] in BROKEN_FILES:
            continue
        period = parse_period(raw["name"])
        modified = raw.get("last_modified") or raw.get("created") or ""
        resource = Resource(year, kind, period, raw["name"].strip(), raw["url"], modified)
        current = selected.get((kind, period))
        if current is None or _format_rank(resource.url) < _format_rank(current.url):
            selected[(kind, period)] = resource
    return list(selected.values())


def fetch_catalog(years: Optional[list[int]] = None) -> list[Resource]:
    """Fetch the list of in-scope files from the data.gov.ro API."""
    resources: list[Resource] = []
    for year in years or sorted(DATASETS):
        response = requests.get(API_URL, params={"id": DATASETS[year]}, timeout=60)
        response.raise_for_status()
        resources.extend(select_resources(year, response.json()["result"]["resources"]))
    return resources
