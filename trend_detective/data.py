"""NASA POWER data access.

Order of preference for a point location:
  1. A bundled snapshot shipped with the app (preset locations; real NASA POWER responses)
  2. A runtime cache of an earlier live request
  3. A live request to the NASA POWER monthly point API

Nothing here ever invents data: if NASA POWER cannot be reached and no saved copy
exists, a DataUnavailable error is raised and the app says so.

AI disclosure: written with help from Claude Code (Anthropic's AI coding assistant). See README, "Use of AI".
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .catalog import COMMUNITY, END_YEAR, LOCATIONS, SEASONS, START_YEAR, VARIABLES, slugify

POINT_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
REGIONAL_URL = "https://power.larc.nasa.gov/api/temporal/monthly/regional"
HEADERS = {"User-Agent": "EarthSystemTrendDetective/2.0 (NASA Space Apps Challenge 2026)"}
FILL_VALUE = -999.0

ROOT = Path(__file__).resolve().parent.parent
BUNDLE_DIR = ROOT / "data" / "bundled"
POINT_BUNDLE_DIR = BUNDLE_DIR / "points"
GRID_FILE = BUNDLE_DIR / "mongolia_grid_annual.csv.gz"
BOUNDARY_FILE = BUNDLE_DIR / "mongolia_boundary.json"
CACHE_DIR = ROOT / ".nasa_power_cache"


class DataUnavailable(RuntimeError):
    """NASA POWER could not be reached and no saved copy exists."""


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------
def fetch_point_payload(lat: float, lon: float, params: list[str] | None = None, timeout: float = 20) -> dict:
    params = params or list(VARIABLES)
    query = {
        "parameters": ",".join(params),
        "community": COMMUNITY,
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start": START_YEAR,
        "end": END_YEAR,
        "format": "JSON",
    }
    resp = requests.get(POINT_URL, params=query, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if "properties" not in payload:
        raise ValueError(f"Unexpected NASA POWER response: {str(payload)[:300]}")
    return payload


def fetch_regional_payload(param: str, box: tuple[float, float, float, float], timeout: float = 120) -> dict:
    lat_min, lat_max, lon_min, lon_max = box
    query = {
        "parameters": param,
        "community": COMMUNITY,
        "latitude-min": lat_min,
        "latitude-max": lat_max,
        "longitude-min": lon_min,
        "longitude-max": lon_max,
        "start": START_YEAR,
        "end": END_YEAR,
        "format": "JSON",
    }
    resp = requests.get(REGIONAL_URL, params=query, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if "features" not in payload:
        raise ValueError(f"Unexpected NASA POWER response: {str(payload)[:300]}")
    return payload


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
def parse_point_payload(payload: dict) -> pd.DataFrame:
    """Tidy table: Variable, Year, Month (1-12, 13 = POWER's annual value), Value."""
    rows = []
    for var, series in payload["properties"]["parameter"].items():
        for key, val in series.items():
            if val is None or float(val) == FILL_VALUE:
                continue
            rows.append((var, int(key[:4]), int(key[4:]), float(val)))
    df = pd.DataFrame(rows, columns=["Variable", "Year", "Month"] + ["Value"])
    return df.sort_values(["Variable", "Year", "Month"]).reset_index(drop=True)


def payload_units(payload: dict) -> dict[str, str]:
    return {k: v.get("units", "") for k, v in payload.get("parameters", {}).items()}


# --------------------------------------------------------------------------
# Point loading with bundle / cache / live fallbacks
# --------------------------------------------------------------------------
def _cache_path(lat: float, lon: float) -> Path:
    key = hashlib.md5(f"{COMMUNITY}|{START_YEAR}|{END_YEAR}|{lat:.4f}|{lon:.4f}".encode()).hexdigest()[:12]
    return CACHE_DIR / f"point_{key}.json"


def bundle_path_for(name: str) -> Path:
    return POINT_BUNDLE_DIR / f"{slugify(name)}.json"


def _bundled_payload(lat: float, lon: float) -> dict | None:
    for name, (plat, plon, _desc) in LOCATIONS.items():
        if abs(plat - lat) < 1e-4 and abs(plon - lon) < 1e-4:
            path = bundle_path_for(name)
            if path.exists():
                return json.loads(path.read_text())
    return None


def _has_all_variables(payload: dict) -> bool:
    return set(VARIABLES) <= set(payload.get("properties", {}).get("parameter", {}))


def load_point(lat: float, lon: float, force_live: bool = False) -> tuple[pd.DataFrame, str]:
    """Return (tidy monthly table, source) where source is 'bundled', 'cached' or 'live'."""
    if not force_live:
        bundled = _bundled_payload(lat, lon)
        if bundled is not None and _has_all_variables(bundled):
            return parse_point_payload(bundled), "bundled"
        path = _cache_path(lat, lon)
        if path.exists():
            try:
                cached = json.loads(path.read_text())
                if _has_all_variables(cached):
                    return parse_point_payload(cached), "cached"
            except (OSError, ValueError):
                pass

    try:
        payload = fetch_point_payload(lat, lon)
    except Exception as exc:  # network down, timeout, API error
        if force_live:
            # fall back to whatever saved copy exists before giving up
            try:
                return load_point(lat, lon, force_live=False)
            except DataUnavailable:
                pass
        raise DataUnavailable(str(exc)) from exc

    try:
        CACHE_DIR.mkdir(exist_ok=True)
        _cache_path(lat, lon).write_text(json.dumps(payload))
    except OSError:
        pass
    return parse_point_payload(payload), "live"


# --------------------------------------------------------------------------
# Seasonal / annual series
# --------------------------------------------------------------------------
def seasonal_series(monthly: pd.DataFrame, var: str, season: str) -> pd.DataFrame:
    """Return Year, Value for one variable and season.

    'Whole year' uses POWER's own annual value (month 13). Seasons combine the monthly
    values with the variable's aggregation (mean, max, min or sum). Winter (Dec-Feb) is
    labelled with the year of its January, so winter 2025 = Dec 2024 + Jan/Feb 2025.
    Seasons with a missing month are dropped.
    """
    sub = monthly[monthly["Variable"] == var]
    months = SEASONS[season]
    if months is None:
        out = sub[sub["Month"] == 13][["Year", "Value"]]
        return out.sort_values("Year").reset_index(drop=True)

    sub = sub[sub["Month"].isin(months)].copy()
    if sub.empty:
        return pd.DataFrame(columns=["Year", "Value"])
    sub["SeasonYear"] = np.where(sub["Month"] == 12, sub["Year"] + 1, sub["Year"]) if 12 in months else sub["Year"]
    agg = VARIABLES[var]["agg"]
    grouped = sub.groupby("SeasonYear")["Value"]
    counts = grouped.count()
    values = getattr(grouped, agg)()
    values = values[counts == len(months)]
    values = values[(values.index >= START_YEAR) & (values.index <= END_YEAR)]
    return pd.DataFrame({"Year": values.index.astype(int), "Value": values.values.round(4)})


# --------------------------------------------------------------------------
# Mongolia grid (bundled) and boundary
# --------------------------------------------------------------------------
def load_boundary() -> list[list[list[list[float]]]]:
    """List of polygons; each polygon is a list of rings; each ring a list of [lon, lat]."""
    return json.loads(BOUNDARY_FILE.read_text())["polygons"]


def points_in_polygons(lons: np.ndarray, lats: np.ndarray, polygons) -> np.ndarray:
    """Even-odd ray casting test for many points against (multi)polygons with holes."""
    lons = np.asarray(lons, dtype=float)
    lats = np.asarray(lats, dtype=float)
    inside_any = np.zeros(lons.shape, dtype=bool)
    for poly in polygons:
        inside = np.zeros(lons.shape, dtype=bool)
        for ring in poly:  # outer ring and holes both toggle
            ring = np.asarray(ring, dtype=float)
            x1, y1 = ring[:, 0], ring[:, 1]
            x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
            for ax, ay, bx, by in zip(x1, y1, x2, y2):
                if ay == by:
                    continue
                crosses = (ay > lats) != (by > lats)
                x_at = ax + (lats - ay) * (bx - ax) / (by - ay)
                inside ^= crosses & (lons < x_at)
        inside_any |= inside
    return inside_any


def grid_available() -> bool:
    return GRID_FILE.exists() and BOUNDARY_FILE.exists()


def load_grid() -> pd.DataFrame:
    """Long table of the bundled Mongolia grid: Variable, Lat, Lon, InMongolia, Year, Value."""
    wide = pd.read_csv(GRID_FILE)
    year_cols = [c for c in wide.columns if c.isdigit()]
    polygons = load_boundary()
    cells = wide[["Lat", "Lon"]].drop_duplicates()
    cells["InMongolia"] = points_in_polygons(cells["Lon"].values, cells["Lat"].values, polygons)
    wide = wide.merge(cells, on=["Lat", "Lon"], how="left")
    long = wide.melt(id_vars=["Variable", "Lat", "Lon", "InMongolia"], value_vars=year_cols, var_name="Year", value_name="Value")
    long["Year"] = long["Year"].astype(int)
    return long.dropna(subset=["Value"]).reset_index(drop=True)


def country_average(grid: pd.DataFrame, var: str) -> pd.DataFrame:
    """Area-weighted (cos latitude) Mongolia average annual series for one variable."""
    sub = grid[(grid["Variable"] == var) & grid["InMongolia"]].copy()
    if sub.empty:
        return pd.DataFrame(columns=["Year", "Value"])
    sub["w"] = np.cos(np.radians(sub["Lat"]))
    sub["wv"] = sub["w"] * sub["Value"]
    g = sub.groupby("Year")[["wv", "w"]].sum()
    return pd.DataFrame({"Year": g.index.astype(int), "Value": (g["wv"] / g["w"]).round(4).values})


def country_monthly_frame(grid: pd.DataFrame) -> pd.DataFrame:
    """Country averages in the same tidy shape as load_point (annual values only, Month = 13)."""
    frames = []
    for var in grid["Variable"].unique():
        ca = country_average(grid, var)
        ca.insert(0, "Variable", var)
        ca.insert(2, "Month", 13)
        frames.append(ca)
    if not frames:
        return pd.DataFrame(columns=["Variable", "Year", "Month", "Value"])
    return pd.concat(frames, ignore_index=True)
