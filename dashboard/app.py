"""Interactive dashboard for the SEAP Lens warehouse.

Run:  streamlit run dashboard/app.py

Reads the Parquet extract in dashboard/data (see `python -m scripts.export_dashboard`).
DASHBOARD_DATA_DIR points it at another directory.
"""

import sys
from pathlib import Path

# `streamlit run` puts this file's directory on the path, not the repository's.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from dashboard import charts, data  # noqa: E402

FIRST_YEAR, LAST_YEAR = 2016, 2022
REPO_URL = "https://github.com/ionutcal/seap-lens"
INDEPENDENCE = "Independent project, with no official link to SEAP, SICAP or any Romanian public authority."
NOT_WRONGDOING = (
    "A single offer does not mean wrongdoing. It can have normal explanations, such as a highly specialized market."
)
SHARE_COLUMNS = ["single_offer_share", "share_low", "share_high", "market_share"]
COLUMN_NAMES = {
    "year": "Year",
    "contracts": "Contracts",
    "single_offer_contracts": "Contracts with one offer",
    "single_offer_share": "One offer (%)",
    "share_low": "95% interval, low (%)",
    "share_high": "95% interval, high (%)",
    "cpv_group": "CPV group",
    "category": "Type of purchase",
    "county": "County",
    "value_kind": "Kind",
    "suspect_contracts": "Suspect contracts",
    "contracted_value_ron": "Contracted value (RON)",
    "suspect_value_ron": "Suspect value (RON)",
    "median_value_ron": "Median value (RON)",
    "supplier_rank": "Rank",
    "supplier_name": "Supplier",
    "value_ron": "Value (RON)",
    "market_share": "Share (%)",
}
GAPS = "Bid counts stop after 2022. 2019 Q2 and 2022 Q1 have none, because of how those files were published."


@st.cache_data(show_spinner=False)
def load(name: str):
    return data.load_table(name)


def plot(figure) -> None:
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})


def readable(frame):
    """Column names and percentages as a reader expects them."""
    result = frame.copy()
    for column in SHARE_COLUMNS:
        if column in result:
            result[column] = (result[column] * 100).round(1)
    return result.rename(columns=COLUMN_NAMES)


def table_view(frame, label: str = "Show the data") -> None:
    with st.expander(label):
        st.dataframe(readable(frame), hide_index=True, width="stretch")


def period_control(key: str) -> tuple[int, int]:
    return st.select_slider(
        "Period", options=list(range(FIRST_YEAR, LAST_YEAR + 1)), value=(2021, LAST_YEAR), key=key
    )


def overview(metadata: dict) -> None:
    by_county = load("competition_by_county")
    yearly = data.yearly_competition(by_county)
    latest = data.period_share(by_county, 2021, LAST_YEAR)

    st.subheader(f"About one in four contracts had a single offer: {latest * 100:.1f}% in 2021–2022")
    st.write(
        "SEAP Lens brings Romanian public procurement files from 2016 onwards into one tested warehouse. "
        f"{NOT_WRONGDOING}"
    )
    first, second, third = st.columns(3)
    first.metric("Contracts with a bid count", f"{metadata['contracts_with_bid_count']:,}")
    second.metric("Awards in the warehouse", f"{metadata['awards']:,}")
    third.metric("Latest award notice", metadata["last_award_date"][:10])

    st.markdown("#### Share of contracts with one offer, by year of the award notice")
    plot(charts.national_share_figure(yearly))
    st.caption(GAPS + " Leaves out procedures with no real competition, such as negotiation without a notice.")
    table_view(yearly[["year", "contracts", "single_offer_contracts", "single_offer_share"]])


def competition() -> None:
    by_county = load("competition_by_county")
    by_cpv = load("competition_by_cpv")
    first_year, last_year = period_control("competition_period")
    national = data.period_share(by_county, first_year, last_year)

    cpv_names = by_cpv.dropna(subset=["cpv_group_name"]).drop_duplicates("cpv_group").set_index("cpv_group").cpv_group_name
    cpv = data.segment_competition(by_cpv, "cpv_group", first_year, last_year)
    cpv["category"] = cpv.cpv_group.map(cpv_names).fillna("Group " + cpv.cpv_group)
    cpv["label"] = cpv.category.map(data.shorten)

    st.markdown("#### By type of purchase")
    if not cpv.empty:
        top = cpv.iloc[0]
        st.write(
            f"**{top.category}** has the highest share, at {top.single_offer_share * 100:.1f}% "
            f"of {top.contracts:,} contracts."
        )
    plot(charts.segment_bars_figure(cpv, "label", national))
    st.caption(
        f"Top-level CPV groups, named as in the source. Groups under {data.MIN_CONTRACTS} contracts are left out. "
        "Shares count contracts, so one large procedure with many contracts can move a group."
    )
    table_view(cpv[["cpv_group", "category", "contracts", "single_offer_share", "share_low", "share_high"]])

    st.markdown("#### By county of the contracting authority")
    county = data.segment_competition(by_county, "county", first_year, last_year)
    plot(charts.segment_bars_figure(county, "county", national))
    st.caption("County comes from the authority's earlier notices. Differences between counties also reflect what they buy.")
    table_view(county[["county", "contracts", "single_offer_share", "share_low", "share_high"]])


def authorities() -> None:
    by_authority = load("competition_by_authority")
    national = data.yearly_competition(load("competition_by_county"))
    totals = by_authority.groupby(["authority_cui", "authority_name"], as_index=False).contracts.sum()
    eligible = totals[totals.contracts >= 30].sort_values("authority_name")

    st.markdown("#### Look up one authority")
    st.write(
        "There is no ranking here on purpose. Without knowing what an authority buys, its share "
        f"can't be judged, so this view only compares it with the national share. {NOT_WRONGDOING}"
    )
    options = dict(zip(eligible.authority_cui, eligible.authority_name))
    selected = st.selectbox(
        "Authority", list(options), format_func=lambda cui: f"{options[cui]} ({cui})",
        help="Only authorities with at least 30 contracts appear.",
    )
    rows = data.with_shares(by_authority[by_authority.authority_cui == selected]).sort_values("year")
    plot(charts.authority_share_figure(rows, national))
    st.caption("Vertical lines show the 95% confidence interval, which is wide when a year has few contracts. " + GAPS)
    table_view(rows[["year", "contracts", "single_offer_contracts", "single_offer_share", "share_low", "share_high"]])


def spending(metadata: dict) -> None:
    value = load("contracted_value")
    partial_year = int(metadata["last_award_date"][:4]) if metadata["last_award_date"][5:7] != "12" else None
    st.warning(
        "These totals come only from SEAP data and have not been compared with an official figure. "
        "Treat them as estimates.",
        icon="⚠️",
    )
    st.markdown("#### Contracted value by contract year")
    plot(charts.contracted_value_figure(value, partial_year))
    st.caption(
        "Real contracts only, counting joint winners once. Framework ceilings are left out, as are "
        f"{metadata['suspect_contracts']:,} contracts with suspect values: zero or negative, above 10 billion RON, "
        "or more than 10 times the estimate. Earlier years can't separate ceilings from real contracts."
    )
    table_view(value.sort_values(["year", "value_kind"]))

    st.markdown("#### Largest suppliers")
    suppliers = load("supplier_concentration")
    left, middle, right = st.columns(3)
    year = left.selectbox("Contract year", sorted(suppliers.year.unique(), reverse=True))
    in_year = suppliers[suppliers.year == year]
    county = middle.selectbox("County", sorted(in_year.county.unique()))
    in_county = in_year[in_year.county == county]
    groups = in_county.drop_duplicates("cpv_group").sort_values("cpv_group")
    labels = {row.cpv_group: data.shorten(f"{row.cpv_group} {row.cpv_group_name or ''}") for row in groups.itertuples()}
    group = right.selectbox("Type of purchase", list(labels), format_func=labels.get)
    top = in_county[in_county.cpv_group == group].sort_values("supplier_rank")
    st.dataframe(readable(top[["supplier_rank", "supplier_name", "value_ron", "market_share"]]), hide_index=True, width="stretch")
    st.caption("Share of the value awarded in this county and purchase type. A high share in a small market can come from one contract.")


def about(metadata: dict) -> None:
    st.markdown(
        f"""
#### What this is

{INDEPENDENCE}

The data comes from the yearly "Achiziții publice" datasets on [data.gov.ro](https://data.gov.ro), published by the
Autoritatea pentru Digitalizarea României. Files from 2016–2020 are under OGL-ROU-1.0, and from 2021 under CC BY 4.0.
The figures here are derived from that data. This extract is from {metadata['exported_on']}.

#### Limits

- **Bid counts:** {GAPS}
- **Republished contracts:** the same contract can appear in several files, so only its latest file counts.
- **What a single offer shows:** {NOT_WRONGDOING}
- **Totals:** contracted value hasn't been compared with an official figure.
- **Suspect values:** the outlier rule is a judgement call and doesn't check every value.

The full method is in the [data validation report]({REPO_URL}/blob/main/docs/data-validation.md).
"""
    )


def main() -> None:
    st.set_page_config(page_title="SEAP Lens", layout="wide")
    metadata = data.load_metadata()
    st.title("SEAP Lens")
    st.caption(f"Romanian public procurement data. {INDEPENDENCE}")
    tabs = st.tabs(["Overview", "Competition", "Authorities", "Contracted value", "About"])
    with tabs[0]:
        overview(metadata)
    with tabs[1]:
        competition()
    with tabs[2]:
        authorities()
    with tabs[3]:
        spending(metadata)
    with tabs[4]:
        about(metadata)


main()
