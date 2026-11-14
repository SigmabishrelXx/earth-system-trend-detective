"""
Earth System Trend Detective
NASA Space Apps Challenge 2026 - "Be An Earth System Trend Detective!"
Team Florensiza - Ulaanbaatar, Mongolia

Run locally:   python3 -m streamlit run app.py
Tests:         python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from trend_detective import catalog as C
from trend_detective.analysis import (
    TrendResult,
    analyze,
    confidence_band,
    format_num,
    format_p,
    grid_trends,
    p_text,
)
from trend_detective.data import (
    DataUnavailable,
    country_average,
    country_monthly_frame,
    grid_available,
    load_boundary,
    load_grid,
    load_point,
    seasonal_series,
)

st.set_page_config(page_title="Earth System Trend Detective", page_icon="🔎", layout="wide")

BLUE, RED, TEAL, GREY = "#2563eb", "#dc2626", "#0d9488", "#6b7280"
PALETTES = {"warm": "RdBu_r", "cold": "RdBu", "wet": "BrBG", "neutral": "PuOr_r"}
SEASON_WORD = {"Whole year": "", "Winter (Dec-Feb)": "winter", "Spring (Mar-May)": "spring",
               "Summer (Jun-Aug)": "summer", "Autumn (Sep-Nov)": "autumn"}
GLOBAL_WARMING_PER_DECADE = 0.2  # IPCC SR1.5 (2018), Chapter 1: ~0.2 °C per decade

# --------------------------------------------------------------------------
# Demo missions (guided examples). Stories ask questions; the app computes the answers.
# --------------------------------------------------------------------------
FREE = "Explore on my own"
MISSIONS: dict[str, dict | None] = {
    FREE: None,
    "1 · Is Mongolia warming?": {
        "loc": C.MONGOLIA_REGION, "var": "T2M", "season": "Whole year", "compare": False,
        "story": "Start big: the average air temperature over the whole country, built from hundreds of NASA grid cells.",
        "steps": ["Read the verdict: is the warming significant?",
                  "Compare the rate with the global average in the Mongolia insights tab.",
                  "Open 'Where is it changing?' to see which parts of Mongolia warm fastest."],
    },
    "2 · Summer vs winter in Ulaanbaatar": {
        "loc": "Ulaanbaatar (capital)", "var": "T2M", "season": "Summer (Jun-Aug)", "compare": False,
        "story": "A yearly average can hide what happens in each season. Detectives look closer.",
        "steps": ["Check the summer trend and its verdict.",
                  "Now change 'Season' in the sidebar to Winter (Dec-Feb). Does the trend keep its direction?",
                  "Why might summers and winters behave differently?"],
    },
    "3 · Warm Arctic, cold Mongolia?": {
        "loc": "Ulaanbaatar (capital)", "loc2": "Arctic (Svalbard, Norway)", "var": "T2M",
        "season": "Winter (Dec-Feb)", "compare": True,
        "story": "The challenge says one variable can trend opposite ways in two regions even when one process connects them. "
                 "Some scientists link fast Arctic warming to cold Eurasian winters (the 'warm Arctic, cold continent' pattern).",
        "steps": ["Compare the two winter temperature trends side by side.",
                  "Are they the same direction? Are both significant?",
                  "Read the Learn tab on why a trend can be real in one place and not in another."],
    },
    "4 · Is northern Mongolia drying out?": {
        "loc": "Lake Khuvsgul (northern taiga)", "loc2": "South Gobi (Dalanzadgad)", "var": "GWETROOT",
        "season": "Whole year", "compare": True,
        "story": "Soil moisture in the root zone decides whether grass grows. Compare the northern taiga with the Gobi.",
        "steps": ["Look at the direction of each trend.",
                  "Which location has the stronger evidence?",
                  "Try 'Snow depth' and 'Precipitation' for Lake Khuvsgul. Do they tell the same story?"],
    },
    "5 · Are Gobi winds slowing down?": {
        "loc": "South Gobi (Dalanzadgad)", "var": "WS2M", "season": "Whole year", "compare": False,
        "story": "Wind lifts the dust storms that reach Ulaanbaatar and beyond. Is the wind in the Gobi changing?",
        "steps": ["Read the change per decade and the verdict.",
                  "Open 'What is changing?' to see every variable at this site ranked by evidence.",
                  "Check the map: is the change local or country-wide?"],
    },
    "6 · Fewer frost days on the steppe?": {
        "loc": "Eastern Steppe (Choibalsan)", "var": "FROST_DAYS", "season": "Whole year", "compare": False,
        "story": "Frost days count the days that drop below 0 °C. Fewer frost days mean a longer growing season.",
        "steps": ["How many frost days per decade are being lost?",
                  "Use the time slider to look only at 2000-2025. Is the trend still significant with fewer years?",
                  "Notice the 'years needed' hint when a trend is not significant."],
    },
}

# --------------------------------------------------------------------------
# Session state defaults and mission handling
# --------------------------------------------------------------------------
DEFAULTS = {
    "mission": FREE,
    "loc": "Ulaanbaatar (capital)",
    "loc2": "South Gobi (Dalanzadgad)",
    "compare": False,
    "var": "T2M",
    "season": "Whole year",
    "years": (C.START_YEAR, C.END_YEAR),
    "custom_lat": 47.9184,
    "custom_lon": 106.9177,
    "live_refreshed": [],
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

HAS_GRID = grid_available()
LOCATION_OPTIONS = ([C.MONGOLIA_REGION] if HAS_GRID else []) + list(C.LOCATIONS) + [C.CUSTOM]
COMPARE_OPTIONS = [o for o in LOCATION_OPTIONS if o != C.CUSTOM]
if st.session_state["loc"] not in LOCATION_OPTIONS:
    st.session_state["loc"] = DEFAULTS["loc"]


def apply_mission() -> None:
    m = MISSIONS.get(st.session_state["mission"])
    if not m:
        return
    st.session_state["loc"] = m["loc"] if m["loc"] in LOCATION_OPTIONS else DEFAULTS["loc"]
    st.session_state["var"] = m["var"]
    st.session_state["season"] = m["season"]
    st.session_state["compare"] = m.get("compare", False)
    if "loc2" in m:
        st.session_state["loc2"] = m["loc2"]
    st.session_state["years"] = (C.START_YEAR, C.END_YEAR)


# --------------------------------------------------------------------------
# Cached data access
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def cached_point(lat: float, lon: float, force_live: bool):
    return load_point(lat, lon, force_live=force_live)


@st.cache_data(show_spinner=False)
def cached_grid() -> pd.DataFrame:
    return load_grid()


@st.cache_data(show_spinner=False)
def cached_country_frame() -> pd.DataFrame:
    return country_monthly_frame(cached_grid())


@st.cache_data(show_spinner=False)
def cached_country_series(var: str) -> pd.DataFrame:
    return country_average(cached_grid(), var)


@st.cache_data(show_spinner=False)
def cached_boundary():
    return load_boundary()


@st.cache_data(show_spinner=False)
def cached_grid_trends(var: str, y0: int, y1: int) -> pd.DataFrame:
    g = cached_grid()
    sub = g[(g["Variable"] == var) & g["InMongolia"]]
    return grid_trends(sub, y0, y1)


def resolve(name: str) -> dict:
    if name == C.MONGOLIA_REGION:
        return {"name": name, "short": "Mongolia (country average)", "kind": "region", "lat": None, "lon": None}
    if name == C.CUSTOM:
        lat, lon = float(st.session_state["custom_lat"]), float(st.session_state["custom_lon"])
        return {"name": name, "short": f"{lat:.2f}°, {lon:.2f}°", "kind": "point", "lat": lat, "lon": lon}
    lat, lon, _ = C.LOCATIONS[name]
    return {"name": name, "short": name, "kind": "point", "lat": lat, "lon": lon}


def get_monthly(loc: dict) -> tuple[pd.DataFrame, str]:
    if loc["kind"] == "region":
        return cached_country_frame(), "grid"
    key = f"{loc['lat']:.4f},{loc['lon']:.4f}"
    force = key in st.session_state["live_refreshed"]
    return cached_point(loc["lat"], loc["lon"], force)


def get_series(loc: dict, var: str, season: str, years: tuple[int, int]) -> tuple[pd.DataFrame, str, str | None]:
    """Return (Year/Value table within years, source, note)."""
    monthly, source = get_monthly(loc)
    note = None
    if loc["kind"] == "region":
        if var not in C.MAP_VARIABLES:
            raise DataUnavailable(
                f"The country average is available for: {', '.join(C.VARIABLES[v]['label'] for v in C.MAP_VARIABLES)}. "
                "Pick one of those, or choose a single location.")
        if season != "Whole year":
            note = "The country average uses yearly values only, so the whole year is shown."
            season = "Whole year"
    s = seasonal_series(monthly, var, season)
    s = s[(s["Year"] >= years[0]) & (s["Year"] <= years[1])].reset_index(drop=True)
    return s, source, note


SOURCE_BADGE = {
    "live": ("🟢", "Live from the NASA POWER API"),
    "cached": ("🟢", "NASA POWER data saved from an earlier live request"),
    "bundled": ("🟢", "NASA POWER data snapshot bundled with the app (downloaded 2026-11-14)"),
    "grid": ("🟢", "Average of NASA POWER grid cells inside Mongolia (bundled snapshot, 2026-11-14)"),
}


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------
def what_phrase(var: str, season: str) -> str:
    word = SEASON_WORD[season]
    label = C.VARIABLES[var]["label"]
    return f"{word.capitalize()} {label.lower()}" if word else label


def verdict_message(r: TrendResult, var: str, season: str, place: str) -> tuple[str, str]:
    meta = C.VARIABLES[var]
    unit = meta["unit"]
    what = what_phrase(var, season)
    rate = format_num(abs(r.per_decade), unit, signed=False)
    tests = f"t-test {p_text(r.p_linear)}, Mann-Kendall {p_text(r.mk.p)}"
    if r.verdict == "significant":
        return "success", (
            f"✅ **Significant trend.** {what} at **{place}** is **{r.direction}** by about **{rate} per decade** "
            f"({r.start}-{r.end}). Both tests agree ({tests}): a run like this would happen by chance less than "
            f"5% of the time, so it is very unlikely to be just random year-to-year ups and downs."
        )
    if r.verdict == "mixed":
        which = "the linear t-test" if r.sig_linear else "the Mann-Kendall test"
        other = "the Mann-Kendall test" if r.sig_linear else "the linear t-test"
        return "warning", (
            f"⚠️ **Possible trend: the tests disagree.** {what} at **{place}** leans **{r.direction}** "
            f"(about {rate} per decade, {r.start}-{r.end}). {which.capitalize()} finds it significant but {other} "
            f"does not ({tests}). Treat it as a lead worth following, not as proof."
        )
    msg = (
        f"➖ **No significant trend.** {what} at **{place}** leans {r.direction} ({format_num(r.per_decade, unit)} "
        f"per decade, {r.start}-{r.end}), but the year-to-year ups and downs are too large to tell this apart "
        f"from chance ({tests})."
    )
    if r.years_needed and r.n < r.years_needed <= 200:
        msg += (f" If this trend and this amount of noise continued, about **{r.years_needed} years** of data would "
                f"be needed to call it significant ({r.years_needed - r.n} more than you have selected).")
    return "info", msg


def show_verdict(r: TrendResult, var: str, season: str, place: str, box=st) -> None:
    kind, msg = verdict_message(r, var, season, place)
    getattr(box, kind)(msg)
    if r.lag1 > 0.3:
        box.caption(f"Note: neighbouring years are correlated (lag-1 r = {r.lag1:.2f}), "
                    "so the p-values may be a little optimistic.")


def verdict_icon(r: TrendResult) -> str:
    return {"significant": "✅", "mixed": "⚠️", "not significant": "➖"}[r.verdict]


def metrics_row(r: TrendResult, unit: str, box=st, compact: bool = False) -> None:
    cols = box.columns(3 if compact else 5)
    cols[0].metric("Change per decade", format_num(r.per_decade, unit),
                   help=f"Linear trend × 10 years. 95% confidence interval: "
                        f"{format_num(r.ci_low * 10, unit)} to {format_num(r.ci_high * 10, unit)}.")
    cols[1].metric(f"Total change ({r.end - r.start} yrs)", format_num(r.total_change, unit),
                   help="Change along the trend line from the first to the last selected year.")
    cols[2].metric("Mann-Kendall p", format_p(r.mk.p),
                   help="Probability of a monotonic trend this strong appearing by chance. Below 0.05 = significant.")
    if not compact:
        cols[3].metric("t-test p", format_p(r.p_linear),
                       help="p-value of the linear regression slope (t-test). Below 0.05 = significant.")
        cols[4].metric("R² fit", f"{r.r2:.2f}",
                       help="Share of the year-to-year variation explained by the straight trend line (0 to 1).")


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
def trend_figure(df: pd.DataFrame, r: TrendResult, var: str, title: str) -> go.Figure:
    unit = C.VARIABLES[var]["unit"]
    years, lo, hi = confidence_band(df, r)
    fit = r.intercept + r.slope * years
    sen_line = np.median(df["Value"] - r.sen_slope * df["Year"]) + r.sen_slope * years
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.concatenate([years, years[::-1]]), y=np.concatenate([hi, lo[::-1]]),
                             fill="toself", fillcolor="rgba(220,38,38,0.12)", line=dict(width=0),
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
                      hovermode="x unified", height=440, margin=dict(l=10, r=10, t=60, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1))
    return fig


def compare_figure(a: pd.DataFrame, ra: TrendResult, name_a: str, b: pd.DataFrame, rb: TrendResult,
                   name_b: str, var: str) -> go.Figure:
    unit = C.VARIABLES[var]["unit"]
    fig = go.Figure()
    for df, r, name, color in ((a, ra, name_a, BLUE), (b, rb, name_b, TEAL)):
        base = df["Value"].mean()
        fig.add_trace(go.Scatter(x=df["Year"], y=df["Value"] - base, mode="lines+markers", name=name,
                                 line=dict(color=color, width=1.5), marker=dict(size=5), opacity=0.75,
                                 hovertemplate="%{x}: %{y:+.3f} " + unit + "<extra>" + name + "</extra>"))
        fit = r.intercept + r.slope * df["Year"] - base
        fig.add_trace(go.Scatter(x=df["Year"], y=fit, mode="lines", name=f"{name} trend",
                                 line=dict(color=color, width=3), hoverinfo="skip"))
    fig.add_hline(y=0, line=dict(color=GREY, width=1, dash="dot"))
    fig.update_layout(title="Both places on one chart (difference from each place's own average)",
                      xaxis_title="Year", yaxis_title=f"Difference from average ({unit})", height=420,
                      hovermode="x unified", margin=dict(l=10, r=10, t=60, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1))
    return fig


def map_figure(tr: pd.DataFrame, var: str, boundary) -> go.Figure:
    meta = C.VARIABLES[var]
    unit = meta["unit"]
    z = tr.pivot(index="Lat", columns="Lon", values="PerDecade").sort_index().sort_index(axis=1)
    lim = float(np.nanpercentile(np.abs(tr["PerDecade"]), 98)) or 1e-6
    fig = go.Figure(go.Heatmap(
        x=z.columns, y=z.index, z=z.values, colorscale=PALETTES[meta["palette"]], zmid=0, zmin=-lim, zmax=lim,
        colorbar=dict(title=dict(text=f"{unit}<br>per decade", side="right")),
        hovertemplate="Lat %{y:.2f}°, Lon %{x:.2f}°<br>%{z:+.3f} " + unit + " per decade<extra></extra>",
    ))
    sig = tr[tr["PMK"] < 0.05]
    fig.add_trace(go.Scatter(x=sig["Lon"], y=sig["Lat"], mode="markers", name="Significant (Mann-Kendall p < 0.05)",
                             marker=dict(size=3, color="#111827"), hoverinfo="skip"))
    for i, poly in enumerate(boundary):
        ring = np.asarray(poly[0])
        fig.add_trace(go.Scatter(x=ring[:, 0], y=ring[:, 1], mode="lines", line=dict(color="#94a3b8", width=2),
                                 name="Mongolia border", showlegend=i == 0, hoverinfo="skip"))
    sites = [(n.split(" (")[0], *C.LOCATIONS[n][:2]) for n in C.MONGOLIA_SITES]
    fig.add_trace(go.Scatter(x=[s[2] for s in sites], y=[s[1] for s in sites], mode="markers+text",
                             text=[s[0] for s in sites], textposition="top center", name="Preset locations",
                             marker=dict(size=9, color="white", line=dict(color="#111827", width=2)),
                             textfont=dict(size=12, color="white", shadow="0px 0px 3px black"), hoverinfo="text"))
    fig.update_xaxes(title="Longitude (°E)", showgrid=False, range=[87.2, 120.4])
    fig.update_yaxes(title="Latitude (°N)", showgrid=False, scaleanchor="x",
                     scaleratio=1 / math.cos(math.radians(47)), range=[41.2, 52.6])
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0))
    return fig


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("🕵️ Start here")
    st.selectbox("Pick a demo mission, or explore freely", list(MISSIONS), key="mission", on_change=apply_mission)

    st.header("1 · Where?")
    st.selectbox("Location", LOCATION_OPTIONS, key="loc")
    if st.session_state["loc"] == C.CUSTOM:
        c1, c2 = st.columns(2)
        c1.number_input("Latitude", -90.0, 90.0, step=0.5, format="%.4f", key="custom_lat")
        c2.number_input("Longitude", -180.0, 180.0, step=0.5, format="%.4f", key="custom_lon")
        st.caption("Any point on Earth works. New places are fetched live from NASA (about 5 seconds).")
    elif st.session_state["loc"] == C.MONGOLIA_REGION:
        st.caption("Area-weighted average of every NASA POWER grid cell inside Mongolia's border.")
    else:
        lat_, lon_, desc_ = C.LOCATIONS[st.session_state["loc"]]
        st.caption(f"{desc_} ({lat_:.2f}°, {lon_:.2f}°)")

    st.header("2 · What?")
    st.selectbox("Earth science variable", list(C.VARIABLES), key="var",
                 format_func=lambda k: f"{C.VARIABLES[k]['theme']} · {C.var_title(k)}")
    st.caption(C.VARIABLES[st.session_state["var"]]["definition"])

    st.header("3 · When?")
    st.selectbox("Season", list(C.SEASONS), key="season",
                 help="Looking at one season removes the yearly cycle and can reveal trends a yearly average hides.")
    st.slider("Years", C.START_YEAR, C.END_YEAR, key="years")

    st.header("4 · Compare (optional)")
    st.checkbox("Compare with a second location", key="compare")
    if st.session_state["compare"]:
        if st.session_state["loc2"] not in COMPARE_OPTIONS:
            st.session_state["loc2"] = DEFAULTS["loc2"]
        st.selectbox("Second location", COMPARE_OPTIONS, key="loc2")

    st.divider()
    if st.button("🔄 Get the latest data from NASA", width="stretch",
                 help="Re-download this location live from the NASA POWER API instead of using the saved copy."):
        for name in {st.session_state["loc"], st.session_state["loc2"]}:
            loc_ = resolve(name)
            if loc_["kind"] == "point":
                key_ = f"{loc_['lat']:.4f},{loc_['lon']:.4f}"
                if key_ not in st.session_state["live_refreshed"]:
                    st.session_state["live_refreshed"].append(key_)
    st.caption("Data: NASA Langley Research Center POWER Project. Built for NASA Space Apps 2026 by Team Florensiza.")

LOC = resolve(st.session_state["loc"])
VAR = st.session_state["var"]
SEASON = st.session_state["season"]
YEARS = tuple(st.session_state["years"])
META = C.VARIABLES[VAR]
UNIT = META["unit"]

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("🔎 Earth System Trend Detective")
st.markdown(
    "Pick a place and an Earth science variable measured by NASA satellites or produced by NASA models, "
    "then find out **what is changing, where, by how much, and whether the change is statistically significant.**"
)

mission = MISSIONS.get(st.session_state["mission"])
if mission:
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(mission["steps"], 1))
    st.info(f"**🕵️ Mission: {st.session_state['mission'].split('· ')[-1]}**  \n{mission['story']}\n\n{steps}")

tab_inv, tab_scan, tab_map, tab_mng, tab_learn = st.tabs(
    ["🔎 Investigate", "🧭 What is changing?", "🗺️ Where is it changing?", "🇲🇳 Mongolia insights", "📚 Learn"]
)


# --------------------------------------------------------------------------
# Tab: Investigate
# --------------------------------------------------------------------------
def render_investigate() -> None:
    try:
        with st.spinner("Getting NASA POWER data..."):
            df, source, note = get_series(LOC, VAR, SEASON, YEARS)
    except DataUnavailable as exc:
        st.error(f"Could not load data for {LOC['short']}. {exc}")
        st.caption("If you are offline, choose one of the preset locations: their NASA data is saved inside the app.")
        return
    icon, text = SOURCE_BADGE[source]
    st.caption(f"{icon} {text}")
    if note:
        st.caption(f"ℹ️ {note}")
    if len(df) < 5:
        st.warning("Please select at least 5 years with data so a trend can be calculated.")
        return
    if df["Year"].min() > YEARS[0]:
        why = (" (winter 1981 would need December 1980)" if SEASON.startswith("Winter") and df["Year"].min() == YEARS[0] + 1
               else "")
        st.caption(f"ℹ️ Data for this selection starts in {df['Year'].min()}{why}.")
    season_eff = "Whole year" if LOC["kind"] == "region" else SEASON

    r = analyze(df)
    st.subheader(f"{what_phrase(VAR, season_eff)} · {LOC['short']}")
    metrics_row(r, UNIT)
    show_verdict(r, VAR, season_eff, LOC["short"])
    st.markdown(f"**Why it matters:** {META['why']}")
    if META["source"] == C.CERES and r.start < C.SOURCE_SWITCH_YEAR <= r.end:
        st.warning(
            f"🔍 **Detective's caution:** NASA POWER switches the source of this variable in {C.SOURCE_SWITCH_YEAR} "
            "(GEWEX SRB before, CERES satellite after). A jump at that year can look like a trend. "
            f"Set the years slider to start at {C.SOURCE_SWITCH_YEAR} to test the CERES-only record."
        )

    title = f"{what_phrase(VAR, season_eff)} at {LOC['short']}, {r.start}-{r.end}"
    st.plotly_chart(trend_figure(df, r, VAR, title), width="stretch")

    with st.expander("🔬 The statistics behind the verdict"):
        rows = [
            ("Linear trend (least squares)", f"{format_num(r.per_decade, UNIT)} per decade",
             f"95% confidence interval {format_num(r.ci_low * 10, UNIT)} to {format_num(r.ci_high * 10, UNIT)}. "
             + ("It does not include zero, so the trend is significant." if r.sig_linear
                else "It includes zero, so 'no change' cannot be ruled out.")),
            ("t-test on the slope", p_text(r.p_linear),
             "Significant" if r.sig_linear else "Not significant"),
            ("Mann-Kendall test", f"{p_text(r.mk.p)}  (S = {r.mk.s:.0f}, Z = {r.mk.z:+.2f}, τ = {r.mk.tau:+.2f})",
             "Significant" if r.sig_mk else "Not significant"),
            ("Sen's slope", f"{format_num(r.sen_slope * 10, UNIT)} per decade",
             f"95% interval {format_num(r.sen_low * 10, UNIT)} to {format_num(r.sen_high * 10, UNIT)}. "
             "A robust trend rate that ignores outliers."),
            ("R² of the trend line", f"{r.r2:.3f}", f"The trend explains {r.r2 * 100:.0f}% of the year-to-year variation."),
            ("Years analysed", f"{r.n} ({r.start}-{r.end})", f"Average value {r.mean:.3f} {UNIT}."),
        ]
        st.dataframe(pd.DataFrame(rows, columns=["Test", "Result", "What it means"]), hide_index=True, width="stretch")
        st.caption("Significance level: 0.05 (5%). A verdict of 'significant' needs both tests to agree.")

    export = df.rename(columns={"Value": f"{VAR} ({UNIT})"})
    export["Linear trend"] = np.round(r.intercept + r.slope * df["Year"], 4)

    if st.session_state["compare"]:
        loc2 = resolve(st.session_state["loc2"])
        st.divider()
        st.subheader(f"⚖️ Compare: {LOC['short']} vs {loc2['short']}")
        try:
            df2, source2, note2 = get_series(loc2, VAR, SEASON, YEARS)
        except DataUnavailable as exc:
            st.error(f"Could not load data for {loc2['short']}. {exc}")
            df2 = None
        if df2 is not None and len(df2) >= 5:
            if LOC["kind"] == "region" or loc2["kind"] == "region":
                if SEASON != "Whole year":
                    st.warning("The country average only has yearly values. Set Season to 'Whole year' for a fair comparison.")
            r2 = analyze(df2)
            season2 = "Whole year" if loc2["kind"] == "region" else SEASON
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**{verdict_icon(r)} {LOC['short']}**")
                metrics_row(r, UNIT, box=c1, compact=True)
            with c2:
                st.markdown(f"**{verdict_icon(r2)} {loc2['short']}**")
                metrics_row(r2, UNIT, box=c2, compact=True)
                show_verdict(r2, VAR, season2, loc2["short"], box=c2)
            if np.sign(r.slope) != np.sign(r2.slope):
                both_sig = r.verdict == "significant" and r2.verdict == "significant"
                st.markdown(
                    f"🔀 **Opposite directions:** {what_phrase(VAR, season_eff).lower()} is {r.direction} at "
                    f"{LOC['short']} but {r2.direction} at {loc2['short']}. "
                    + ("Both trends are significant." if both_sig else
                       "At least one of the two trends is not significant, so the contrast is a lead, not proof.")
                    + " The same large-scale process can push a variable in opposite directions in different regions."
                )
            else:
                st.markdown(f"↔️ **Same direction:** both places are {r.direction}. "
                            f"{LOC['short']}: {format_num(r.per_decade, UNIT)} per decade; "
                            f"{loc2['short']}: {format_num(r2.per_decade, UNIT)} per decade.")
            st.plotly_chart(compare_figure(df, r, LOC["short"], df2, r2, loc2["short"], VAR), width="stretch")
            export = export.merge(df2.rename(columns={"Value": f"{VAR} ({UNIT}) at {loc2['short']}"}), on="Year", how="outer")
        elif df2 is not None:
            st.warning(f"Not enough data at {loc2['short']} for this selection.")

    with st.expander("📋 Data table and download"):
        st.dataframe(export, hide_index=True, width="stretch")
        st.download_button("⬇️ Download CSV", export.to_csv(index=False).encode("utf-8"),
                           file_name=f"trend_{VAR}_{C.slugify(LOC['short'])}_{YEARS[0]}-{YEARS[1]}.csv",
                           mime="text/csv")


# --------------------------------------------------------------------------
# Tab: What is changing? (scan every variable)
# --------------------------------------------------------------------------
def scan_all(loc: dict, season: str, years: tuple[int, int]) -> list[tuple[str, pd.DataFrame, TrendResult]]:
    found = []
    for var in C.VARIABLES:
        try:
            df, _, _ = get_series(loc, var, season, years)
        except DataUnavailable:
            continue
        if len(df) < 5 or df["Value"].std() == 0:
            continue
        found.append((var, df, analyze(df)))
    return found


def render_scan() -> None:
    season_eff = "Whole year" if LOC["kind"] == "region" else SEASON
    st.markdown(f"Every variable at **{LOC['short']}** "
                f"({SEASON_WORD[season_eff] or 'whole year'}, {YEARS[0]}-{YEARS[1]}), ranked by strength of evidence.")
    try:
        with st.spinner("Testing every variable..."):
            results = scan_all(LOC, SEASON, YEARS)
    except DataUnavailable as exc:
        st.error(str(exc))
        return
    if not results:
        st.warning("No variables have enough data for this selection.")
        return
    order = {"significant": 0, "mixed": 1, "not significant": 2}
    results.sort(key=lambda t: (order[t[2].verdict], -abs(t[2].mk.z)))
    n_sig = sum(r.verdict == "significant" for _, _, r in results)
    st.metric("Variables with a significant trend", f"{n_sig} of {len(results)}")

    rows = []
    for var, _, r in results:
        meta = C.VARIABLES[var]
        pct = r.percent_per_decade if meta["unit"] not in ("°C",) else None
        rows.append({
            "Verdict": f"{verdict_icon(r)} {r.verdict}",
            "Variable": meta["label"],
            "Change per decade": format_num(r.per_decade, meta["unit"]),
            "% of average per decade": f"{pct:+.1f}%" if pct is not None else "",
            "Direction": {"increasing": "↑ up", "decreasing": "↓ down", "flat": "→ flat"}[r.direction],
            "Mann-Kendall p": format_p(r.mk.p),
            "t-test p": format_p(r.p_linear),
            "Data source": C.SHORT_SOURCE[meta["source"]],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    top = [t for t in results if t[2].verdict == "significant"][:6]
    if top:
        st.markdown("**Strongest signals**")
        for var, _, r in top[:3]:
            meta = C.VARIABLES[var]
            st.markdown(f"- **{what_phrase(var, season_eff)}** is {r.direction} by "
                        f"{format_num(abs(r.per_decade), meta['unit'], signed=False)} per decade "
                        f"(Mann-Kendall {p_text(r.mk.p)}). {meta['why']}")
        ncols = 3
        nrows = math.ceil(len(top) / ncols)
        fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=[C.var_title(v) for v, _, _ in top],
                            vertical_spacing=0.18 if nrows > 1 else 0.1)
        for i, (var, df, r) in enumerate(top):
            row, col = i // ncols + 1, i % ncols + 1
            fig.add_trace(go.Scatter(x=df["Year"], y=df["Value"], mode="lines", line=dict(color=BLUE, width=1.5),
                                     showlegend=False, hovertemplate="%{x}: %{y:.3f}<extra></extra>"), row=row, col=col)
            fig.add_trace(go.Scatter(x=df["Year"], y=r.intercept + r.slope * df["Year"], mode="lines",
                                     line=dict(color=RED, width=2), showlegend=False, hoverinfo="skip"), row=row, col=col)
        fig.update_layout(height=260 * nrows, margin=dict(l=10, r=10, t=40, b=10))
        fig.update_annotations(font_size=12)
        st.plotly_chart(fig, width="stretch")
    st.caption("Tip: pick any variable from this list in the sidebar to investigate it in detail. "
               f"Sunlight and cloud cover change data source in {C.SOURCE_SWITCH_YEAR}, so check their trends "
               f"from {C.SOURCE_SWITCH_YEAR} onward too. Testing many variables means about 1 in 20 can look "
               "significant by chance.")


# --------------------------------------------------------------------------
# Tab: Where is it changing? (Mongolia map)
# --------------------------------------------------------------------------
def area_share(tr: pd.DataFrame, mask: pd.Series) -> float:
    w = np.cos(np.radians(tr["Lat"]))
    return float(w[mask].sum() / w.sum() * 100) if len(tr) else 0.0


def render_map() -> None:
    if not HAS_GRID:
        st.info("The Mongolia map needs the bundled grid file. Run `python3 scripts/build_bundled_data.py grid`.")
        return
    default = VAR if VAR in C.MAP_VARIABLES else "T2M"
    var = st.selectbox("Variable to map", C.MAP_VARIABLES, index=C.MAP_VARIABLES.index(default),
                       format_func=C.var_title)
    meta = C.VARIABLES[var]
    unit = meta["unit"]
    st.markdown(f"Trend per decade in **{meta['label'].lower()}** for every NASA POWER grid cell inside Mongolia "
                f"(about 50 km apart), yearly values {YEARS[0]}-{YEARS[1]}. Dots mark cells where the "
                "Mann-Kendall test finds a significant trend.")
    with st.spinner("Testing every grid cell..."):
        tr = cached_grid_trends(var, YEARS[0], YEARS[1])
    if tr.empty:
        st.warning("Not enough years selected for the map.")
        return
    nat = cached_country_series(var)
    nat = nat[(nat["Year"] >= YEARS[0]) & (nat["Year"] <= YEARS[1])]
    rn = analyze(nat) if len(nat) >= 5 else None
    sig = tr["PMK"] < 0.05
    c1, c2, c3, c4 = st.columns(4)
    if rn:
        c1.metric("Mongolia average, per decade", format_num(rn.per_decade, unit),
                  help=f"Area-weighted country average. Mann-Kendall {p_text(rn.mk.p)}.")
    c2.metric("Area with significant increase", f"{area_share(tr, sig & (tr['PerDecade'] > 0)):.0f}%")
    c3.metric("Area with significant decrease", f"{area_share(tr, sig & (tr['PerDecade'] < 0)):.0f}%")
    c4.metric("Grid cells tested", f"{len(tr)}")
    st.plotly_chart(map_figure(tr, var, cached_boundary()), width="stretch")
    fastest = tr.loc[tr["PerDecade"].idxmax()]
    slowest = tr.loc[tr["PerDecade"].idxmin()]
    st.caption(
        f"Largest increase: {format_num(fastest.PerDecade, unit)} per decade near {fastest.Lat:.1f}°N {fastest.Lon:.1f}°E. "
        f"Largest decrease: {format_num(slowest.PerDecade, unit)} per decade near {slowest.Lat:.1f}°N {slowest.Lon:.1f}°E. "
        "Grid: NASA POWER native resolution (0.5° × 0.625° for MERRA-2 variables, 1° for solar). "
        "Border: Natural Earth (public domain)."
    )


# --------------------------------------------------------------------------
# Tab: Mongolia insights
# --------------------------------------------------------------------------
INSIGHT_VARS = ["T2M", "FROST_DAYS", "PRECTOTCORR", "GWETROOT", "SNODP", "WS2M"]


def render_mongolia() -> None:
    st.markdown(f"Key Mongolian climate signals computed live from NASA POWER data for **{YEARS[0]}-{YEARS[1]}**. "
                "Numbers update when you change the years in the sidebar.")
    if HAS_GRID:
        st.subheader("Mongolia as a whole")
        cols = st.columns(len(INSIGHT_VARS))
        temp_r = None
        for col, var in zip(cols, INSIGHT_VARS):
            nat = cached_country_series(var)
            nat = nat[(nat["Year"] >= YEARS[0]) & (nat["Year"] <= YEARS[1])]
            if len(nat) < 5:
                continue
            r = analyze(nat)
            if var == "T2M":
                temp_r = r
            col.metric(f"{verdict_icon(r)} {C.VARIABLES[var]['label']}",
                       format_num(r.per_decade, C.VARIABLES[var]["unit"]) + "/dec",
                       help=f"Country average, per decade. Mann-Kendall {p_text(r.mk.p)}; verdict: {r.verdict}.")
        if temp_r:
            tr_t = cached_grid_trends("T2M", YEARS[0], YEARS[1])
            warm_share = area_share(tr_t, (tr_t["PMK"] < 0.05) & (tr_t["PerDecade"] > 0)) if len(tr_t) else 0
            cool_share = area_share(tr_t, (tr_t["PMK"] < 0.05) & (tr_t["PerDecade"] < 0)) if len(tr_t) else 0
            st.markdown(
                f"🌡️ Averaged over the whole country, air temperature changed by **{format_num(temp_r.per_decade, '°C')} "
                f"per decade** ({temp_r.verdict}), about **{format_num(temp_r.total_change, '°C')}** over "
                f"{temp_r.end - temp_r.start} years. **{warm_share:.0f}%** of Mongolia's area shows significant warming "
                f"and **{cool_share:.0f}%** significant cooling. For context, the IPCC puts the current global average "
                f"warming (land and ocean together) at about {GLOBAL_WARMING_PER_DECADE} °C per decade; land usually "
                "warms faster than the ocean."
            )

    st.subheader("Seasons tell different stories")
    rows = []
    for site in C.MONGOLIA_SITES:
        lat, lon, _ = C.LOCATIONS[site]
        try:
            monthly, _ = cached_point(lat, lon, False)
        except DataUnavailable:
            continue
        for season in list(C.SEASONS)[1:]:
            s = seasonal_series(monthly, "T2M", season)
            s = s[(s["Year"] >= YEARS[0]) & (s["Year"] <= YEARS[1])]
            if len(s) >= 5:
                r = analyze(s)
                rows.append((site.split(" (")[0], SEASON_WORD[season], r.per_decade, r.verdict == "significant"))
    if rows:
        sdf = pd.DataFrame(rows, columns=["Site", "Season", "PerDecade", "Significant"])
        fig = go.Figure()
        colors = {"winter": "#3b82f6", "spring": "#22c55e", "summer": "#ef4444", "autumn": "#f59e0b"}
        for season, color in colors.items():
            d = sdf[sdf["Season"] == season]
            fig.add_trace(go.Bar(
                x=d["Site"], y=d["PerDecade"], name=season.capitalize(), marker_color=color,
                marker_opacity=[1.0 if s else 0.35 for s in d["Significant"]],
                marker_line=dict(color=["#111827" if s else "rgba(0,0,0,0)" for s in d["Significant"]], width=1.5),
                hovertemplate="%{x}, " + season + ": %{y:+.2f} °C per decade<extra></extra>"))
        fig.add_hline(y=0, line=dict(color=GREY, width=1))
        fig.update_layout(barmode="group", height=400, yaxis_title="Air temperature change (°C per decade)",
                          margin=dict(l=10, r=10, t=30, b=10),
                          legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1))
        st.plotly_chart(fig, width="stretch")
        st.caption("Solid bars with an outline are significant (both tests agree); faded bars are not.")
        summer = sdf[sdf["Season"] == "summer"]
        winter = sdf[sdf["Season"] == "winter"]
        st.markdown(
            f"☀️ **Summer:** {int(summer['Significant'].sum())} of {len(summer)} Mongolian sites show significant "
            f"warming (average {summer['PerDecade'].mean():+.2f} °C per decade).  \n"
            f"❄️ **Winter:** {int(winter['Significant'].sum())} of {len(winter)} sites show a significant trend "
            f"(average {winter['PerDecade'].mean():+.2f} °C per decade). A yearly average mixes these together, "
            "which is why looking season by season matters."
        )

    st.subheader("Site by site")
    season_eff = SEASON
    table = []
    for site in C.MONGOLIA_SITES:
        lat, lon, _ = C.LOCATIONS[site]
        try:
            monthly, _ = cached_point(lat, lon, False)
        except DataUnavailable:
            continue
        row = {"Site": site}
        for var in INSIGHT_VARS:
            s = seasonal_series(monthly, var, season_eff)
            s = s[(s["Year"] >= YEARS[0]) & (s["Year"] <= YEARS[1])]
            if len(s) < 5 or s["Value"].std() == 0:
                row[C.var_title(var)] = ""
                continue
            r = analyze(s)
            row[C.var_title(var)] = f"{verdict_icon(r)} {format_num(r.per_decade, '')}"
        table.append(row)
    st.markdown(f"Change per decade, {SEASON_WORD[season_eff] or 'whole year'} (✅ significant, ⚠️ tests disagree, ➖ not significant):")
    st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")

    with st.expander("🧩 What could these trends mean for Mongolia?"):
        st.markdown(
            "- **Dzud (harsh winters):** summer drought followed by deep snow or extreme cold can kill millions of "
            "livestock. Watch summer soil moisture, winter snow depth and the lowest temperatures together.\n"
            "- **Desertification:** drier root-zone soil, less precipitation and stronger winds favour degraded "
            "pasture and dust storms, especially in the Gobi.\n"
            "- **Permafrost:** northern Mongolia sits on the southern edge of Siberian permafrost. Warmer summers "
            "and fewer frost days can thaw it, affecting rivers, lakes and buildings.\n"
            "- **Herding and farming:** a longer frost-free season can help crops, but heat and dry soil can hurt "
            "pasture growth.\n\n"
            "These are hypotheses to explore with the data, not conclusions. A trend in one variable is a clue; "
            "detectives look for several clues that point the same way."
        )


# --------------------------------------------------------------------------
# Tab: Learn
# --------------------------------------------------------------------------
def render_learn() -> None:
    st.subheader("How to be a trend detective")
    st.markdown(
        "1. **Choose a suspect:** a variable that might be changing (temperature, rain, soil moisture...). "
        "The *What is changing?* tab tests them all at once.\n"
        "2. **Choose the scene:** a place or the whole of Mongolia. Trends are usually regional, not global.\n"
        "3. **Look at the evidence:** the time series chart shows each year's value and the trend line.\n"
        "4. **Test it:** is the trend bigger than natural year-to-year variability? The app runs two tests."
    )
    st.subheader("The statistics, in plain words")
    st.markdown(
        "- **Trend (rate of change):** the slope of the best straight line through the yearly values, shown per "
        "decade (10 years).\n"
        "- **p-value:** if nothing were really changing, how often would random ups and downs produce a trend at "
        "least this strong? A p-value below **0.05** (5%) is called **statistically significant**.\n"
        "- **t-test:** tests whether the slope of the straight line is different from zero. It assumes the "
        "scatter around the line is roughly bell-shaped.\n"
        "- **95% confidence interval:** the range of trend rates that fit the data. If it does not include "
        "zero, the trend is significant.\n"
        "- **Mann-Kendall test:** compares every year with every later year and counts ups versus downs. It does "
        "not assume a straight line or bell-shaped scatter, so one extreme year cannot fool it. Widely used for "
        "climate and hydrology data.\n"
        "- **Sen's slope:** the median of the slopes between every pair of years. A robust trend rate that "
        "goes with the Mann-Kendall test.\n"
        "- **R²:** how much of the year-to-year variation the trend line explains (0 = none, 1 = all).\n"
        "- **Why two tests?** When both agree, the evidence is strong. When they disagree, treat the trend as a "
        "lead to investigate further.\n"
        "- **Not significant does not mean no change.** Sometimes a trend only needs a longer record. The app "
        "estimates how many years would be needed if the trend continued."
    )
    st.subheader("Why can a trend go opposite ways in two places?")
    st.markdown(
        "The Earth system is connected. Warming can make one region wetter and another drier as storm tracks and "
        "monsoons shift, and Arctic warming may change the jet stream in a way that brings colder winters to parts "
        "of Asia. That is why the app lets you compare two places side by side and map trends across Mongolia."
    )
    st.subheader("Variables")
    glossary = pd.DataFrame([
        {"Variable": m["label"], "Unit": m["unit"], "What it measures": m["definition"],
         "Why it matters": m["why"], "Data source": m["source"], "NASA POWER code": k}
        for k, m in C.VARIABLES.items()
    ])
    st.dataframe(glossary, hide_index=True, width="stretch")
    st.subheader("Data and methods")
    st.markdown(
        "- **Data:** [NASA POWER](https://power.larc.nasa.gov) (Prediction Of Worldwide Energy Resources), "
        "monthly and annual API, version 2.x. Meteorology and soil variables come from NASA GMAO's **MERRA-2** "
        "reanalysis model (which assimilates satellite observations); sunlight and cloud cover come from the "
        "**CERES** satellite instruments (SYN1deg, 2001+) and **GEWEX SRB** (1984-2000).\n"
        "- **Period:** 1981-2025 (sunlight and cloud from 1984).\n"
        "- **Yearly values** are NASA POWER's annual values. **Seasons** combine the monthly values (mean, or "
        "maximum/minimum/total for extremes and frost days). Winter = December of the previous year + January + February.\n"
        "- **Mongolia average and map:** every NASA POWER grid cell whose centre lies inside Mongolia's border, "
        "weighted by cell area (cosine of latitude).\n"
        "- **Tests:** least-squares regression with t-test and 95% confidence interval (SciPy), Mann-Kendall test "
        "with tie correction, and Sen's slope (SciPy). Significance level 0.05.\n"
        "- **Limitations:** reanalysis grid cells are about 50 km wide, so they describe a region, not a single "
        "weather station. The tests look for steady (linear or monotonic) trends only; they assume independent "
        "years, and strong year-to-year memory can make p-values too optimistic. Testing many variables at once "
        "means about 1 in 20 could look significant by chance. Sunlight and cloud cover switch from GEWEX SRB to "
        "CERES in 2001, so a step at that year can create a false trend; test 2001-2025 separately."
    )
    st.subheader("Credits")
    st.markdown(
        "- Data: NASA Langley Research Center (LaRC) POWER Project, funded through the NASA Earth Science Applied "
        "Sciences Program.\n"
        "- Starting code: [kdmayer/nasa-power-api](https://github.com/kdmayer/nasa-power-api) by Kevin Mayer (MIT License).\n"
        "- Country border: [Natural Earth](https://www.naturalearthdata.com) (public domain).\n"
        "- Built with Streamlit, Plotly, pandas, NumPy and SciPy for the 2026 NASA Space Apps Challenge by Team "
        "Florensiza (Ulaanbaatar, Mongolia). AI assistance: see the README."
    )


with tab_inv:
    render_investigate()
with tab_scan:
    render_scan()
with tab_map:
    render_map()
with tab_mng:
    render_mongolia()
with tab_learn:
    render_learn()
