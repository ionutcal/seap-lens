"""Plotly figures for the dashboard. Each returns a figure without a title, which the view writes."""

import pandas as pd
import plotly.graph_objects as go

FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
INK = "#0b0b0b"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
VALUE_KIND_NAMES = {"standalone_contract": "Standalone contracts", "subsequent_contract": "Contracts under a framework"}


def _theme(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=30, t=30, b=10),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, size=13, color=INK),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        hoverlabel=dict(font_family=FONT, bgcolor="white"),
    )
    fig.update_xaxes(showgrid=False, linecolor=BASELINE, tickcolor=BASELINE)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=BASELINE)
    return fig


def national_share_figure(yearly: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=yearly.year,
            y=yearly.single_offer_share * 100,
            mode="lines+markers",
            line=dict(color=BLUE, width=2),
            marker=dict(size=9, color=BLUE, line=dict(color=SURFACE, width=2)),
            customdata=yearly.contracts,
            hovertemplate="%{x}: %{y:.1f}% of %{customdata:,} contracts<extra></extra>",
        )
    )
    _theme(fig)
    fig.update_xaxes(dtick=1, tickformat="d")
    fig.update_yaxes(title_text="Contracts with one offer (%)", rangemode="tozero")
    return fig


def segment_bars_figure(segments: pd.DataFrame, label: str, national: float) -> go.Figure:
    """Horizontal bars, highest first, with the national share as a reference line."""
    ordered = segments.iloc[::-1]
    fig = go.Figure(
        go.Bar(
            x=ordered.single_offer_share * 100,
            y=ordered[label],
            orientation="h",
            marker=dict(color=BLUE, cornerradius=4),
            customdata=ordered[["contracts", "share_low", "share_high"]].assign(
                share_low=ordered.share_low * 100, share_high=ordered.share_high * 100
            ),
            hovertemplate=(
                "%{y}: %{x:.1f}% of %{customdata[0]:,} contracts"
                "<br>95% interval: %{customdata[1]:.1f}–%{customdata[2]:.1f}%<extra></extra>"
            ),
        )
    )
    _theme(fig, height=max(280, 24 * len(ordered) + 70))
    fig.add_vline(
        x=national * 100, line=dict(color=INK, width=1, dash="dot"),
        annotation_text=f"National {national * 100:.1f}%", annotation_position="top",
        annotation_font=dict(size=12, color=INK),
    )
    fig.update_layout(bargap=0.3)
    fig.update_xaxes(title_text="Contracts with one offer (%)", showgrid=True, gridcolor=GRID, rangemode="tozero")
    fig.update_yaxes(showgrid=False, automargin=True, type="category")
    return fig


def authority_share_figure(authority: pd.DataFrame, national: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=national.year, y=national.single_offer_share * 100, name="All authorities",
            mode="lines", line=dict(color=ORANGE, width=2),
            hovertemplate="All authorities, %{x}: %{y:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=authority.year, y=authority.single_offer_share * 100, name="This authority",
            mode="lines+markers", line=dict(color=BLUE, width=2),
            marker=dict(size=9, color=BLUE, line=dict(color=SURFACE, width=2)),
            error_y=dict(
                type="data", symmetric=False, thickness=1, width=4, color=BLUE,
                array=(authority.share_high - authority.single_offer_share) * 100,
                arrayminus=(authority.single_offer_share - authority.share_low) * 100,
            ),
            customdata=authority.contracts,
            hovertemplate="This authority, %{x}: %{y:.1f}% of %{customdata:,} contracts<extra></extra>",
        )
    )
    _theme(fig, height=340)
    fig.update_xaxes(dtick=1, tickformat="d")
    fig.update_yaxes(title_text="Contracts with one offer (%)", range=[0, 100])
    return fig


def contracted_value_figure(value: pd.DataFrame, partial_year: int | None) -> go.Figure:
    fig = go.Figure()
    for kind, color in (("standalone_contract", BLUE), ("subsequent_contract", ORANGE)):
        rows = value[value.value_kind == kind].sort_values("year")
        fig.add_trace(
            go.Bar(
                x=rows.year.astype(str), y=rows.contracted_value_ron / 1e9, name=VALUE_KIND_NAMES[kind],
                marker=dict(color=color, line=dict(color=SURFACE, width=2)),
                customdata=rows.contracts,
                hovertemplate="%{x}: %{y:.1f} billion RON, %{customdata:,} contracts<extra>" + VALUE_KIND_NAMES[kind] + "</extra>",
            )
        )
    _theme(fig)
    fig.update_layout(barmode="stack", bargap=0.45)
    fig.update_yaxes(title_text="Billion RON")
    totals = value.groupby("year").contracted_value_ron.sum() / 1e9
    for year, total in totals.items():
        fig.add_annotation(x=str(year), y=total, text=f"{total:.0f}", showarrow=False, yshift=12, font=dict(size=13, color=INK))
    if partial_year is not None:
        fig.update_xaxes(tickvals=[str(y) for y in sorted(value.year.unique())],
                         ticktext=[f"{y} (partial)" if y == partial_year else str(y) for y in sorted(value.year.unique())])
    return fig
