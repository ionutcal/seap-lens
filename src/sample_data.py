"""A small set of SEAP rows that exercises each warehouse rule, for tests and the docs site."""

from pathlib import Path

import pandas as pd

from src.schema import standardize
from src.standardize import clean, save_parquet


def contract(notice, number, winner="1", value="100", through="Fara acord cadru", bids=None, date="2023-05-01 00:00:00",
             procedure="Licitatie deschisa", participation=None):
    return {
        "Numar anunt atribuire": notice, "Data anunt atribuire": date, "Numar anunt initiere": participation,
        "Data contract": date, "Numar contract": number, "Numar lot": "1", "Tip contract": "Furnizare",
        "Tip procedura": procedure, "Incheiat prin": through, "CUI autoritate contractanta": "RO 9",
        "Autoritate contractanta": "Primaria", "CUI ofertant castigator": winner, "Ofertant castigator": f"Firma {winner}",
        "Valoare contract (RON)": value, "Numar oferte": bids, "Cod CPV": "33600000-6", "Denumire CPV": "Medicamente",
    }


def notice(identifier, value="5", county="Cluj"):
    return {
        "Numar anunt initiere": identifier, "Data publicare": "2023-01-02 10:00:00",
        "CUI autoritate contractanta": "9", "Autoritate contractanta": "Primaria", "Judet": county,
        "Tip contract": "Furnizare", "Tip procedura": "Licitatie deschisa", "Valoare estimata": value, "Moneda": "RON",
        "Cod CPV": "33600000-6", "Denumire CPV": "Medicamente",
    }


CONTRACT_FILES = {
    (2021, "Q1"): [
        contract("CAN7", "7", bids="1", date="2021-02-01 00:00:00"),
        contract("CAN7", "7", winner="2", bids="1", date="2021-02-01 00:00:00"),
        contract("CAN8", "8", bids="1", date="2021-02-01 00:00:00"),
        contract("CAN8", "8", winner="2", bids="3", date="2021-02-01 00:00:00"),
        contract("CAN9", "9", bids="1", date="2021-02-01 00:00:00", procedure="Negociere fara anunt de participare"),
    ],
    (2023, "Q3"): [
        contract("CAN1", "1", value="1,000"),
        contract("CAN2", "2", winner="1", value="500"),
        contract("CAN2", "2", winner="2", value="500"),
        contract("CAN3", "3", value="9000000000", through="Cu acord cadru"),
        contract("CAN4", "4", value="100", through="Cu acord cadru subsecvent"),
        contract("CAN5", "5", value="200000000000"),
        contract("CAN6", "6", value="1000", participation="CN6"),
    ],
    # CAN1 is republished with a new value, and a 2023 contract appears in a later file.
    (2024, "Q1"): [contract("CAN1", "1", value="2000")],
}
NOTICE_FILES = {(2023, "Q3"): [notice("CN6", value="10"), notice("CN6", value="10")]}


def write_sample_data(root: Path) -> None:
    """Write the sample rows as standardized Parquet under root/standard, the layout dbt reads."""
    for kind, files in (("contracts", CONTRACT_FILES), ("notices", NOTICE_FILES)):
        for (year, period), rows in files.items():
            typed, rejects = clean(standardize(pd.DataFrame(rows), kind), kind)
            if not rejects.empty:
                raise ValueError(f"Sample {kind} rows were rejected: {rejects.reject_reason.tolist()}")
            typed["file_year"], typed["file_period"], typed["source_sha256"] = year, period, "sample"
            save_parquet(typed, root / "standard" / kind / f"{year}_{period}.parquet")
