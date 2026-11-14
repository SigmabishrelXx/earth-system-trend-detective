"""Trend statistics.

Three complementary checks, as suggested in the challenge brief:
  * Ordinary least-squares linear trend with a t-test and a 95% confidence interval
  * Mann-Kendall test (non-parametric, robust to outliers and non-normal data)
  * Sen's slope (median of all pairwise slopes) with its 95% confidence interval
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

ALPHA = 0.05


@dataclass
class MannKendall:
    s: float
    var_s: float
    z: float
    p: float
    tau: float


@dataclass
class TrendResult:
    n: int
    start: int
    end: int
    mean: float
    slope: float  # units per year (OLS)
    intercept: float
    stderr: float
    ci_low: float  # 95% CI of OLS slope, units per year
    ci_high: float
    p_linear: float
    r2: float
    mk: MannKendall
    sen_slope: float  # units per year
    sen_low: float
    sen_high: float
    resid_std: float
    lag1: float  # lag-1 autocorrelation of residuals
    years_needed: int | None  # record length needed to reach significance, if not yet significant

    @property
    def per_decade(self) -> float:
        return self.slope * 10

    @property
    def total_change(self) -> float:
        return self.slope * (self.end - self.start)

    @property
    def sig_linear(self) -> bool:
        return self.p_linear < ALPHA

    @property
    def sig_mk(self) -> bool:
        return self.mk.p < ALPHA

    @property
    def verdict(self) -> str:
        """'significant' (both tests agree), 'mixed' (only one test) or 'not significant'."""
        same_sign = np.sign(self.slope) == np.sign(self.mk.s) or self.mk.s == 0
        if self.sig_linear and self.sig_mk and same_sign:
            return "significant"
        if self.sig_linear or self.sig_mk:
            return "mixed"
        return "not significant"

    @property
    def direction(self) -> str:
        if self.slope > 0:
            return "increasing"
        if self.slope < 0:
            return "decreasing"
        return "flat"

    @property
    def percent_per_decade(self) -> float | None:
        if abs(self.mean) < 1e-9:
            return None
        return self.per_decade / abs(self.mean) * 100


def mann_kendall(values) -> MannKendall:
    """Classic two-sided Mann-Kendall test with tie correction and continuity correction."""
    x = np.asarray(values, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 3:
        return MannKendall(0.0, 0.0, 0.0, 1.0, 0.0)
    diffs = x[None, :] - x[:, None]
    s = float(np.sign(diffs[np.triu_indices(n, k=1)]).sum())
    _, counts = np.unique(x, return_counts=True)
    ties = counts[counts > 1]
    var_s = (n * (n - 1) * (2 * n + 5) - float(np.sum(ties * (ties - 1) * (2 * ties + 5)))) / 18.0
    if var_s <= 0:
        return MannKendall(s, var_s, 0.0, 1.0, 0.0)
    if s > 0:
        z = (s - 1) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    p = float(2 * stats.norm.sf(abs(z)))
    tau = s / (n * (n - 1) / 2)
    return MannKendall(s, var_s, z, p, tau)


def years_needed_for_significance(slope: float, resid_std: float, alpha: float = ALPHA, max_years: int = 500) -> int | None:
    """Shortest record length (consecutive years) for which this slope and noise would give p < alpha.

    Uses the OLS slope standard error for evenly spaced years: SE = s / sqrt(n(n^2-1)/12).
    Assumes the trend and the year-to-year noise stay the same, so it is only a rough guide.
    """
    if slope == 0 or resid_std <= 0 or not np.isfinite(slope):
        return None
    n = np.arange(5, max_years + 1, dtype=float)
    se = resid_std / np.sqrt(n * (n * n - 1) / 12.0)
    t_crit = stats.t.ppf(1 - alpha / 2, n - 2)
    ok = np.nonzero(abs(slope) / se >= t_crit)[0]
    return int(n[ok[0]]) if len(ok) else None


def analyze(df: pd.DataFrame) -> TrendResult:
    """Run every test on a Year/Value table (at least 5 rows)."""
    df = df.dropna(subset=["Value"]).sort_values("Year")
    years = df["Year"].to_numpy(dtype=float)
    values = df["Value"].to_numpy(dtype=float)
    n = len(values)
    if n < 5:
        raise ValueError("At least 5 years are needed for a trend.")

    lr = stats.linregress(years, values)
    t_crit = stats.t.ppf(1 - ALPHA / 2, n - 2)
    fitted = lr.intercept + lr.slope * years
    resid = values - fitted
    resid_std = float(np.sqrt(np.sum(resid**2) / (n - 2)))
    lag1 = float(np.corrcoef(resid[:-1], resid[1:])[0, 1]) if n > 3 and np.std(resid) > 0 else 0.0

    sen = stats.theilslopes(values, years, alpha=1 - ALPHA)
    mk = mann_kendall(values)

    result = TrendResult(
        n=n,
        start=int(years.min()),
        end=int(years.max()),
        mean=float(values.mean()),
        slope=float(lr.slope),
        intercept=float(lr.intercept),
        stderr=float(lr.stderr),
        ci_low=float(lr.slope - t_crit * lr.stderr),
        ci_high=float(lr.slope + t_crit * lr.stderr),
        p_linear=float(lr.pvalue),
        r2=float(lr.rvalue**2),
        mk=mk,
        sen_slope=float(sen.slope),
        sen_low=float(sen.low_slope),
        sen_high=float(sen.high_slope),
        resid_std=resid_std,
        lag1=lag1,
        years_needed=None,
    )
    if result.verdict != "significant":
        result.years_needed = years_needed_for_significance(result.slope, resid_std)
    return result


def confidence_band(df: pd.DataFrame, r: TrendResult) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """95% confidence band of the fitted trend line. Returns (years, lower, upper)."""
    years = df["Year"].to_numpy(dtype=float)
    x_mean = years.mean()
    sxx = np.sum((years - x_mean) ** 2)
    t_crit = stats.t.ppf(1 - ALPHA / 2, r.n - 2)
    fit = r.intercept + r.slope * years
    half = t_crit * r.resid_std * np.sqrt(1 / r.n + (years - x_mean) ** 2 / sxx)
    return years, fit - half, fit + half


def grid_trends(grid_var: pd.DataFrame, year_min: int, year_max: int) -> pd.DataFrame:
    """Per-cell trend for a long grid table (Lat, Lon, Year, Value) of one variable."""
    sub = grid_var[(grid_var["Year"] >= year_min) & (grid_var["Year"] <= year_max)]
    out = []
    for (lat, lon), cell in sub.groupby(["Lat", "Lon"], sort=False):
        cell = cell.sort_values("Year")
        if len(cell) < 5:
            continue
        y = cell["Year"].to_numpy(dtype=float)
        v = cell["Value"].to_numpy(dtype=float)
        lr = stats.linregress(y, v)
        mk = mann_kendall(v)
        sen = stats.theilslopes(v, y).slope
        out.append((lat, lon, lr.slope * 10, sen * 10, lr.pvalue, mk.p))
    return pd.DataFrame(out, columns=["Lat", "Lon", "PerDecade", "SenPerDecade", "PLinear", "PMK"])


def format_p(p: float) -> str:
    if p < 0.0001:
        return "< 0.0001"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.3f}"


def p_text(p: float) -> str:
    """'p < 0.0001' or 'p = 0.012' for use inside sentences."""
    s = format_p(p)
    return f"p {s}" if s.startswith("<") else f"p = {s}"


def format_num(x: float, unit: str = "", digits: int | None = None, signed: bool = True) -> str:
    if digits is None:
        ax = abs(x)
        digits = 2 if ax >= 1 else 3 if ax >= 0.01 else 4
    s = f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"
    return f"{s} {unit}".strip()
