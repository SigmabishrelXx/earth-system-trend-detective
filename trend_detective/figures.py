"""Plotly figures shared by the Streamlit app and the interactive web slides.

AI disclosure: written with help from Claude Code (Anthropic's AI coding assistant). See README, "Use of AI".
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import catalog as C
from .analysis import TrendResult, confidence_band

BLUE, RED, TEAL, GREY = "#3b82f6", "#ef4444", "#14b8a6", "#94a3b8"
HOT = "#ff6b4a"
PALETTES = {"warm": "RdBu_r", "cold": "RdBu", "wet": "BrBG", "neutral": "PuOr_r"}
SEASON_COLORS = {"winter": "#3b82f6", "spring": "#22c55e", "summer": "#ef4444", "autumn": "#f59e0b"}
MAP_X_RANGE, MAP_Y_RANGE = [87.2, 120.4], [41.2, 52.6]
KEEP = dict(marker=dict(opacity=1))  # stop Plotly dimming traces when a map cell is selected


def _site_points():
    return [(n.split(" (")[0], *C.LOCATIONS[n][:2]) for n in C.MONGOLIA_SITES]


def _map_axes(fig: go.Figure, height: int = 560) -> None:
    fig.update_xaxes(title="Longitude (°E)", showgrid=False, zeroline=False, range=MAP_X_RANGE)
    fig.update_yaxes(title="Latitude (°N)", showgrid=False, zeroline=False, scaleanchor="x",
                     scaleratio=1 / math.cos(math.radians(47)), range=MAP_Y_RANGE)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0))


def _add_border_and_sites(fig: go.Figure, boundary, with_sites: bool = True) -> None:
    for i, poly in enumerate(boundary):
        ring = np.asarray(poly[0])
        fig.add_trace(go.Scatter(x=ring[:, 0], y=ring[:, 1], mode="lines", line=dict(color="#94a3b8", width=2),
                                 name="Mongolia border", showlegend=i == 0, hoverinfo="skip", unselected=KEEP))
    if with_sites:
        sites = _site_points()
        fig.add_trace(go.Scatter(x=[s[2] for s in sites], y=[s[1] for s in sites], mode="markers+text",
                                 text=[s[0] for s in sites], textposition="top center", name="Preset locations",
                                 marker=dict(size=9, color="white", line=dict(color="#111827", width=2)),
                                 textfont=dict(size=12, color="white", shadow="0px 0px 3px black"),
                                 hoverinfo="text", unselected=dict(marker=dict(opacity=1), textfont=dict(color="white"))))


def trend_figure(df: pd.DataFrame, r: TrendResult, var: str, title: str, height: int = 440) -> go.Figure:
    unit = C.VARIABLES[var]["unit"]
    years, lo, hi = confidence_band(df, r)
    fit = r.intercept + r.slope * years
    sen_line = np.median(df["Value"] - r.sen_slope * df["Year"]) + r.sen_slope * years
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.concatenate([years, years[::-1]]), y=np.concatenate([hi, lo[::-1]]),
                             fill="toself", fillcolor="rgba(239,68,68,0.14)", line=dict(width=0),
                             name="95% confidence band", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=df["Year"], y=df["Value"], mode="lines+markers", name="Measured value",
                             line=dict(color=BLUE, width=2), marker=dict(size=6),
                             hovertemplate="%{x}: %{y:.3f} " + unit + "<extra></extra>"))
    fig.add_trace(go.Scatter(x=years, y=fit, mode="lines", name="Linear trend",
                             line=dict(color=RED, width=2.5),
                             hovertemplate="Trend %{x}: %{y:.3f} " + unit + "<extra></extra>"))
    fig.add_trace(go.Scatter(x=years, y=sen_line, mode="lines", name="Sen's slope", visible="legendonly",
                             line=dict(color=GREY, width=2, dash="dot"),
                             hovertemplate="Sen %{x}: %{y:.3f} " + unit + "<extra></extra>"))
    fig.update_layout(title=title, xaxis_title="Year", yaxis_title=f"{C.VARIABLES[var]['label']} ({unit})",
                      hovermode="x unified", height=height, margin=dict(l=10, r=10, t=60, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1))
    return fig


def compare_figure(a: pd.DataFrame, ra: TrendResult, name_a: str, b: pd.DataFrame, rb: TrendResult,
                   name_b: str, var: str, height: int = 420) -> go.Figure:
    unit = C.VARIABLES[var]["unit"]
    fig = go.Figure()
    for df, r, name, color in ((a, ra, name_a, BLUE), (b, rb, name_b, HOT)):
        base = df["Value"].mean()
        fig.add_trace(go.Scatter(x=df["Year"], y=df["Value"] - base, mode="lines+markers", name=name,
                                 line=dict(color=color, width=1.5), marker=dict(size=5), opacity=0.75,
                                 hovertemplate="%{x}: %{y:+.2f} " + unit + "<extra>" + name + "</extra>"))
        fit = r.intercept + r.slope * df["Year"] - base
        fig.add_trace(go.Scatter(x=df["Year"], y=fit, mode="lines", name=f"{name} trend",
                                 line=dict(color=color, width=3.5), hoverinfo="skip"))
    fig.add_hline(y=0, line=dict(color=GREY, width=1, dash="dot"))
    fig.update_layout(title="Both places on one chart (difference from each place's own average)",
                      xaxis_title="Year", yaxis_title=f"Difference from average ({unit})", height=height,
                      hovermode="x unified", margin=dict(l=10, r=10, t=60, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1))
    return fig


def map_figure(tr: pd.DataFrame, var: str, boundary, picked: tuple[float, float] | None = None,
               height: int = 560) -> go.Figure:
    """Trend-per-decade heatmap of Mongolia. An invisible marker on every cell makes cells hoverable/clickable."""
    meta = C.VARIABLES[var]
    unit = meta["unit"]
    z = tr.pivot(index="Lat", columns="Lon", values="PerDecade").sort_index().sort_index(axis=1)
    lim = float(np.nanpercentile(np.abs(tr["PerDecade"]), 98)) or 1e-6
    fig = go.Figure(go.Heatmap(
        x=z.columns, y=z.index, z=z.values, colorscale=PALETTES[meta["palette"]], zmid=0, zmin=-lim, zmax=lim,
        colorbar=dict(title=dict(text=f"{unit}<br>per decade", side="right")), hoverinfo="skip",
    ))
    sig = tr[tr["PMK"] < 0.05]
    fig.add_trace(go.Scatter(x=sig["Lon"], y=sig["Lat"], mode="markers", name="Significant (Mann-Kendall p < 0.05)",
                             marker=dict(size=3, color="#0b0f17"), hoverinfo="skip", unselected=KEEP))
    _add_border_and_sites(fig, boundary)
    verdict = np.where(tr["PMK"] < 0.05, "significant", "not significant")
    fig.add_trace(go.Scatter(
        x=tr["Lon"], y=tr["Lat"], mode="markers", name="cells", showlegend=False,
        marker=dict(size=14, symbol="square", color="rgba(0,0,0,0)"),
        customdata=np.stack([tr["PerDecade"], tr["PMK"], verdict], axis=-1),
        hovertemplate=("%{y:.2f}°N, %{x:.2f}°E<br><b>%{customdata[0]:+.3f} " + unit + " per decade</b>"
                       "<br>Mann-Kendall p = %{customdata[1]:.3f} (%{customdata[2]})<extra>Click to explore</extra>"),
        selected=dict(marker=dict(color="rgba(0,0,0,0)")), unselected=dict(marker=dict(color="rgba(0,0,0,0)")),
    ))
    if picked:
        fig.add_trace(go.Scatter(x=[picked[1]], y=[picked[0]], mode="markers", name="Selected cell",
                                 marker=dict(size=18, symbol="square-open", color="white", line=dict(width=3)),
                                 hoverinfo="skip", unselected=KEEP))
    _map_axes(fig, height)
    return fig


def anomaly_animation(grid_var: pd.DataFrame, var: str, boundary, baseline: tuple[int, int] = (1981, 2010),
                      height: int = 600) -> go.Figure:
    """Year-by-year map of the difference from each cell's 1981-2010 average, with Play and a year slider."""
    meta = C.VARIABLES[var]
    unit = meta["unit"]
    g = grid_var.copy()
    base = g[(g["Year"] >= baseline[0]) & (g["Year"] <= baseline[1])].groupby(["Lat", "Lon"])["Value"].mean()
    g = g.join(base.rename("Base"), on=["Lat", "Lon"])
    g["Anom"] = g["Value"] - g["Base"]
    g = g.dropna(subset=["Anom"])
    lats = np.sort(g["Lat"].unique())
    lons = np.sort(g["Lon"].unique())
    years = np.sort(g["Year"].unique())
    lim = float(np.nanpercentile(np.abs(g["Anom"]), 98)) or 1e-6
    w = np.cos(np.radians(g["Lat"]))
    g["wa"] = g["Anom"] * w
    g["w"] = w
    national = (g.groupby("Year")["wa"].sum() / g.groupby("Year")["w"].sum()).to_dict()

    def z_for(year):
        sub = g[g["Year"] == year].pivot(index="Lat", columns="Lon", values="Anom")
        return sub.reindex(index=lats, columns=lons).values

    def title_for(year):
        return (f"<b>{year}</b> · Mongolia average {national[year]:+.2f} {unit} "
                f"compared with {baseline[0]}-{baseline[1]}")

    first = years[0]
    heat = go.Heatmap(x=lons, y=lats, z=z_for(first), colorscale=PALETTES[meta["palette"]], zmid=0,
                      zmin=-lim, zmax=lim, colorbar=dict(title=dict(text=f"{unit}<br>vs normal", side="right")),
                      hovertemplate="%{y:.2f}°N, %{x:.2f}°E<br>%{z:+.2f} " + unit + " vs normal<extra></extra>")
    fig = go.Figure(data=[heat])
    _add_border_and_sites(fig, boundary)
    fig.frames = [go.Frame(name=str(y), data=[go.Heatmap(z=z_for(y))], traces=[0],
                           layout=go.Layout(title=dict(text=title_for(y)))) for y in years]
    steps = [dict(method="animate", label=str(y),
                  args=[[str(y)], dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))])
             for y in years]
    fig.update_layout(
        title=dict(text=title_for(first)),
        updatemenus=[dict(type="buttons", direction="left", x=0.0, y=-0.04, xanchor="left", yanchor="top",
                          pad=dict(r=10, t=10), showactive=False,
                          buttons=[dict(label="▶ Play", method="animate",
                                        args=[None, dict(frame=dict(duration=280, redraw=True), fromcurrent=True,
                                                         transition=dict(duration=0))]),
                                   dict(label="❚❚ Pause", method="animate",
                                        args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
        sliders=[dict(active=0, x=0.18, y=-0.02, len=0.82, xanchor="left", yanchor="top", pad=dict(t=10),
                      currentvalue=dict(prefix="Year: ", font=dict(size=14)), steps=steps)],
    )
    _map_axes(fig, height)
    fig.update_xaxes(title=None)
    fig.update_layout(margin=dict(l=10, r=10, t=60, b=95))
    return fig


def seasons_figure(sdf: pd.DataFrame, height: int = 400) -> go.Figure:
    """Grouped bars of temperature trend per season per site; faded bars are not significant."""
    fig = go.Figure()
    for season, color in SEASON_COLORS.items():
        d = sdf[sdf["Season"] == season]
        fig.add_trace(go.Bar(
            x=d["Site"], y=d["PerDecade"], name=season.capitalize(), marker_color=color,
            marker_opacity=[1.0 if s else 0.35 for s in d["Significant"]],
            marker_line=dict(color=["#e8edf5" if s else "rgba(0,0,0,0)" for s in d["Significant"]], width=1.5),
            customdata=np.where(d["Significant"], "significant", "not significant"),
            hovertemplate="%{x}, " + season + ": %{y:+.2f} °C per decade (%{customdata})<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=GREY, width=1))
    fig.update_layout(barmode="group", height=height, yaxis_title="Air temperature change (°C per decade)",
                      margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1))
    return fig


def slide_style(fig: go.Figure, height: int | None = None, font_size: int = 16) -> go.Figure:
    """Dark, transparent styling for figures shown outside Streamlit (the web slides)."""
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="-apple-system, 'Helvetica Neue', Arial, sans-serif", color="#e8edf5",
                                size=font_size),
                      hoverlabel=dict(font_size=font_size))
    fig.update_xaxes(gridcolor="rgba(148,163,184,0.15)")
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.15)")
    if height:
        fig.update_layout(height=height)
    return fig
