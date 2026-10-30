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
FEATURE_NAMES = {
    "cpv_group": "type of purchase",
    "contract_type": "contract type",
    "procedure_type": "procedure type",
    "authority_type": "authority type",
    "log_estimated_value": "estimated value",
    "publication_month": "publication month",
    "log_history_contracts": "authority history size",
    "history_single_share": "authority single-offer history",
}
UNVALIDATED = (
    "These scores are unvalidated. Bid counts stop after 2022, so nobody can check them against real outcomes."
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
    "notices": "Scored notices",
    "mean_risk": "Mean estimated risk (%)",
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

    st.markdown("#### Compared with what the model expected, 2021–2022")
    expected = load("authority_expected")
    comparison = data.compare_with_expected(expected[expected.authority_cui == selected])
    if comparison is None:
        st.write(f"Not enough contracts to compare: at least {data.MIN_AUTHORITY_CONTRACTS} are needed.")
    else:
        first, second, third = st.columns(3)
        first.metric("Actual single-offer share", f"{comparison['actual'] * 100:.1f}%")
        second.metric("Expected by the model", f"{comparison['expected'] * 100:.1f}%")
        third.metric("Contracts", f"{comparison['contracts']:,}")
        st.write(
            f"This authority is **{comparison['reading']}** what the model expected. The 95% interval of its actual "
            f"share is {comparison['low'] * 100:.1f}–{comparison['high'] * 100:.1f}%. "
            "This is a deviation from a statistical expectation, not a finding about the authority."
        )

    st.markdown("#### Estimated risk from 2023")
    st.warning(UNVALIDATED, icon="⚠️")
    risk = load("authority_risk")
    rows = risk[risk.authority_cui == selected].sort_values("year")
    if rows.empty:
        st.write("No scored notices from this authority since 2023.")
    else:
        table_view(rows.assign(mean_risk=(rows.mean_risk * 100).round(1))[["year", "notices", "mean_risk"]], "Show the estimated risk")


def feature_list(features: list[str]) -> str:
    return ", ".join(FEATURE_NAMES[feature] for feature in features) or "none"


def model() -> None:
    results = data.load_model_results()
    test = results["test"]
    tested, baseline = test["model"], test["baseline"]
    names = {"mean_rate": "Mean rate", "logistic": "Logistic regression", "lightgbm": "LightGBM"}

    st.markdown("#### Can a single offer be predicted from what is known at publication?")
    st.write(
        f"Partly. On {tested['rows']:,} contracts from 2022 that it had never seen, {names[test['selected']].lower()} scored "
        f"a PR-AUC of {tested['pr_auc']:.3f}, against {baseline['pr_auc']:.3f} for a simple average "
        f"and a base rate of {tested['base_rate']:.3f}. That is useful, but far from certain, and many "
        "single offers remain hard to foresee."
    )
    first, second, third = st.columns(3)
    first.metric("PR-AUC on the 2022 test", f"{tested['pr_auc']:.3f}", help=f"95% interval {tested['pr_auc_low']:.3f}–{tested['pr_auc_high']:.3f}")
    second.metric("Simple average", f"{baseline['pr_auc']:.3f}")
    third.metric("Calibration error", f"{tested['calibration_error'] * 100:.1f} points")

    st.markdown("#### Predicted against actual, on the 2022 test")
    plot(charts.calibration_figure(load("calibration")))
    st.caption("Close to the dotted line means a predicted 30% really happens about 30% of the time. Few contracts get a prediction above 60%, so the last points are less reliable. The test ran once, after the model was chosen.")

    st.markdown("#### How the model was chosen, on 2021")
    variants = results["validation"]["variants"]
    st.dataframe(
        [
            {"Variant": names[name], "PR-AUC": f"{values['pr_auc']:.3f}", "Calibration error (points)": f"{values['calibration_error'] * 100:.1f}"}
            for name, values in variants.items()
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"{names[results['validation']['selected']]} was chosen. A more complex variant had to gain at least 0.02 PR-AUC "
        "without worse calibration, a rule set before seeing any results."
    )

    st.markdown("#### Scores from 2023")
    st.warning(UNVALIDATED, icon="⚠️")
    drift = results["drift"]
    st.dataframe(
        [
            {
                "Year": year,
                "Scored notices": values["procedures"],
                "Mean estimated risk (%)": round(values["mean_risk"] * 100, 1),
                "Inputs that changed (PSI above 0.25)": feature_list(values["above_warning"]),
            }
            for year, values in drift.items()
            if year != "reference_2022"
        ],
        hide_index=True,
        width="stretch",
    )
    reference = feature_list(drift["reference_2022"]["above_warning"])
    st.caption(
        f"Compared per procedure with the training data. The 2022 test data shows a similar change ({reference}), "
        "so this isn't a new break, but later accuracy can't be measured."
    )


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
- **The model:** it predicts from what is known at publication, and scores from 2023 can't be validated.

The full method is in the [data validation report]({REPO_URL}/blob/main/docs/data-validation.md).
"""
    )


def main() -> None:
    st.set_page_config(page_title="SEAP Lens", layout="wide")
    metadata = data.load_metadata()
    st.title("SEAP Lens")
    st.caption(f"Romanian public procurement data. {INDEPENDENCE}")
    tabs = st.tabs(["Overview", "Competition", "Authorities", "Model", "Contracted value", "About"])
    with tabs[0]:
        overview(metadata)
    with tabs[1]:
        competition()
    with tabs[2]:
        authorities()
    with tabs[3]:
        model()
    with tabs[4]:
        spending(metadata)
    with tabs[5]:
        about(metadata)


main()
