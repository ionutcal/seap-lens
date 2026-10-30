"""Plotly figures for the dashboard. Each returns a figure without a title, which the view writes."""

from html import escape

import pandas as pd
import plotly.graph_objects as go

FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
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


def segment_bars_html(segments: pd.DataFrame, label: str, national: float) -> str:
    """Ranked bars in HTML, because category names reach 135 characters and must stay readable.

    A label sits beside its bar on a wide screen and wraps above it on a phone, which a Plotly
    axis can't do. Hovering over a row shows its contracts and confidence interval.
    """
    scale = max(segments.single_offer_share.max(), national) * 100
    marker = national * 100 / scale * 100
    rows = []
    for row in segments.itertuples():
        share = row.single_offer_share * 100
        title = (
            f"{getattr(row, label)}: {share:.1f}% of {row.contracts:,} contracts. "
            f"95% interval: {row.share_low * 100:.1f}–{row.share_high * 100:.1f}%"
        )
        rows.append(
            f'''<div title="{escape(title, quote=True)}" style="display:flex;flex-wrap:wrap;align-items:center;column-gap:12px;padding:4px 0">'''
            f'''<div style="flex:1 1 260px;min-width:0;font-size:13px;line-height:1.3;color:{INK_SECONDARY}">{escape(str(getattr(row, label)))}</div>'''
            f'''<div style="flex:2 1 260px;display:flex;align-items:center;gap:8px;min-width:0">'''
            f'''<div style="position:relative;flex:1;height:14px">'''
            f'''<div style="height:14px;width:{share / scale * 100:.2f}%;background:{BLUE};border-radius:0 4px 4px 0"></div>'''
            f'''<div style="position:absolute;top:-5px;bottom:-5px;left:{marker:.2f}%;border-left:1px dotted {INK}"></div>'''
            f'''</div><div style="flex:0 0 44px;text-align:right;font-size:13px;font-variant-numeric:tabular-nums;color:{INK}">{share:.1f}%</div>'''
            "</div></div>"
        )
    legend = f'''<div style="font-size:12px;color:{INK_SECONDARY};padding-bottom:6px">Dotted line: national share, {national * 100:.1f}%</div>'''
    return f'''<div style="background:{SURFACE};padding:12px 16px;border-radius:8px">{legend}{"".join(rows)}</div>'''


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


def calibration_figure(calibration: pd.DataFrame) -> go.Figure:
    """Actual rate against predicted rate, where the dotted line means a perfectly calibrated model."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[0, 1], y=[0, 100], mode="lines", name="Perfect calibration", hoverinfo="skip",
            line=dict(color=INK_MUTED, width=1, dash="dot"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=calibration.predicted, y=calibration.actual * 100, mode="lines+markers", name="Model on 2022",
            line=dict(color=BLUE, width=2), marker=dict(size=9, color=BLUE, line=dict(color=SURFACE, width=2)),
            customdata=calibration.contracts,
            hovertemplate="Predicted %{x:.0%}: actually %{y:.1f}% of %{customdata:,} contracts<extra></extra>",
        )
    )
    _theme(fig, height=360)
    fig.update_xaxes(title_text="Predicted probability", tickformat=".0%", range=[0, 1], showgrid=True, gridcolor=GRID)
    fig.update_yaxes(title_text="Contracts with one offer (%)", range=[0, 100])
    return fig
