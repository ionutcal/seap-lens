import pytest

from src.catalog import classify_kind, parse_period, select_resources


@pytest.mark.parametrize(
    "name",
    [
        "Contracte-2016-S1.csv",
        "Contracte 2017 - T1",
        " Contracte 2022 T2 ",
        "Contracte publicate T 1 - 2023",
        "Raport Contracte publicate T II 2024",
        "Contracte T IV",
        "Contracte TII 2026",
    ],
)
def test_classifies_contract_files(name):
    assert classify_kind(name) == "contracts"


@pytest.mark.parametrize(
    "name",
    [
        "Anunturi participare 2016.xls",
        "Anunturi participare 2017 - T1",
        "Anunturi initiere - T2",
        "Anunțuri inițiere 2020 - T1",
        "Anunturi de initiere 2022 T2 ",
        "Raport Anunțuri de inițiere publicate T IV 2023.xls",
        "Anunturi de intiere publicate TII 2026",
    ],
)
def test_classifies_notice_files(name):
    assert classify_kind(name) == "notices"


@pytest.mark.parametrize(
    "name",
    [
        "Contracte subsecvente-2016-S1.csv",
        "Date din modificare contract T IV 2023.xlsx",
        "Anunțuri de atribuire la proceduri fără anunț de inițiere T 1 - 2023",
        "Invitații de depunere SAD cu anunț aferent T1 2025",
        "Invitatii de participare 2016.xls",
        "Achizitii directe T III 2023",
        "Notificari de atribuire la cumpararea directa T III 2023",
    ],
)
def test_ignores_other_files(name):
    assert classify_kind(name) is None


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Contracte-2016-S1.csv", "S1"),
        ("Contracte 2017 - T4", "Q4"),
        ("Contracte publicate T 1 - 2023", "Q1"),
        ("Contracte publicate T III 2023", "Q3"),
        ("Contracte TII 2026", "Q2"),
        ("Contracte T IV", "Q4"),
        ("Anunțuri de inițiere publicate T1 2025", "Q1"),
        ("Anunturi participare 2016.xls", "Y"),
    ],
)
def test_parses_period(name, expected):
    assert parse_period(name) == expected


def raw(name, filename):
    return {"name": name, "url": f"https://data.gov.ro/x/{filename}"}


def test_select_prefers_csv_when_a_period_has_two_formats():
    selected = select_resources(
        2023,
        [
            raw("Contracte publicate T III 2023", "c.xls"),
            raw("Contracte publicate T III 2023", "c.csv"),
        ],
    )
    assert [r.url.rsplit("/", 1)[-1] for r in selected] == ["c.csv"]


def test_select_skips_the_truncated_2024_q1_csv():
    selected = select_resources(
        2024,
        [
            raw("Contracte publicate T I 2024", "datagov-raport-contracte-publicate-t-i-2024.csv"),
            raw("Contracte publicate T I 2024", "datagov-raport-contracte-publicate-t-i-2024.xls"),
        ],
    )
    assert [r.filename for r in selected] == ["datagov-raport-contracte-publicate-t-i-2024.xls"]


def test_select_drops_the_2019_q2_file_that_copies_q3():
    assert select_resources(2019, [raw("Contracte 2019 - T2", "raport-t-2-2019.xls")]) == []


def test_select_keeps_year_kind_period_and_drops_other_files():
    selected = select_resources(
        2026,
        [raw("Contracte TII 2026", "c.ods"), raw("Achizitii directe TII 2026", "d.xlsx")],
    )
    assert len(selected) == 1
    assert (selected[0].year, selected[0].kind, selected[0].period) == (2026, "contracts", "Q2")
