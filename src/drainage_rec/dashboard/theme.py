"""Colours and shared Plotly styling for the dashboard."""

import plotly.graph_objects as go

SERIES = {"rain_1d": "#2a78d6", "rain_3d": "#eb6834"}
SERIES_LABEL = {"rain_1d": "1-day rainfall", "rain_3d": "3-day accumulated"}

# Status colours are reserved for tiers and always shown with an icon + label.
TIER_COLOR = {"Normal": "#0ca30c", "Watch": "#fab219", "Alert": "#ec835a", "Emergency": "#d03b3b"}
TIER_ICON = {"Normal": "✓", "Watch": "◔", "Alert": "▲", "Emergency": "⬣"}

SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
INK, INK_2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


def style(fig: go.Figure, height: int = 360, **layout) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=72, b=8),
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK_2, size=13),
        plot_bgcolor="#fcfcfb",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="#fcfcfb", font_color=INK),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
        **layout,
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, tickfont_color=MUTED, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, tickfont_color=MUTED, zeroline=False)
    return fig
