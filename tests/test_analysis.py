"""Run with:  python3 -m unittest discover -s tests -v

AI disclosure: written with help from Claude Code (Anthropic's AI coding assistant). See README, "Use of AI".
"""

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trend_detective.analysis import (  # noqa: E402
    analyze,
    confidence_band,
    grid_trends,
    mann_kendall,
    years_needed_for_significance,
)
from trend_detective.catalog import MAP_VARIABLES, SEASONS, VARIABLES  # noqa: E402
from trend_detective.data import parse_point_payload, points_in_polygons, seasonal_series  # noqa: E402


class MannKendallTests(unittest.TestCase):
    def test_strictly_increasing_textbook_values(self):
        mk = mann_kendall(np.arange(10))
        self.assertEqual(mk.s, 45)
        self.assertAlmostEqual(mk.var_s, 125.0)
        self.assertAlmostEqual(mk.z, 44 / math.sqrt(125))
        self.assertAlmostEqual(mk.p, 2 * stats.norm.sf(44 / math.sqrt(125)))
        self.assertAlmostEqual(mk.tau, 1.0)

    def test_decreasing_is_negative(self):
        mk = mann_kendall(np.arange(20)[::-1])
        self.assertLess(mk.s, 0)
        self.assertLess(mk.z, 0)
        self.assertLess(mk.p, 0.001)

    def test_matches_scipy_kendalltau_without_ties(self):
        rng = np.random.default_rng(1)
        for _ in range(20):
            x = rng.normal(size=40) + np.linspace(0, rng.normal(), 40)
            mk = mann_kendall(x)
            kt = stats.kendalltau(np.arange(40), x, method="asymptotic")
            self.assertAlmostEqual(mk.tau, kt.statistic, places=10)
            # MK applies a continuity correction, so p-values differ only slightly
            self.assertLess(abs(mk.p - kt.pvalue), 0.02)

    def test_tie_correction_reduces_variance(self):
        x = [1, 2, 2, 3, 3, 3, 4, 5, 5, 6]
        mk = mann_kendall(x)
        n = len(x)
        self.assertLess(mk.var_s, n * (n - 1) * (2 * n + 5) / 18)
        # ties of size 2,3,2 -> sum t(t-1)(2t+5) = 18 + 66 + 18 = 102
        self.assertAlmostEqual(mk.var_s, (n * (n - 1) * (2 * n + 5) - 102) / 18)

    def test_constant_series(self):
        mk = mann_kendall([3.0] * 12)
        self.assertEqual(mk.p, 1.0)


class AnalyzeTests(unittest.TestCase):
    def make(self, slope, noise, n=41, seed=0):
        rng = np.random.default_rng(seed)
        years = np.arange(1985, 1985 + n)
        return pd.DataFrame({"Year": years, "Value": 10 + slope * (years - years[0]) + rng.normal(0, noise, n)})

    def test_clear_trend_is_significant_and_ci_covers_truth(self):
        r = analyze(self.make(0.05, 0.3))
        self.assertEqual(r.verdict, "significant")
        self.assertLess(r.ci_low, 0.05)
        self.assertGreater(r.ci_high, 0.05)
        self.assertAlmostEqual(r.per_decade, r.slope * 10)
        self.assertAlmostEqual(r.total_change, r.slope * 40)
        self.assertLess(r.sen_low, r.sen_slope)
        self.assertGreater(r.sen_high, r.sen_slope)
        self.assertIsNone(r.years_needed)
        self.assertEqual(r.direction, "increasing")

    def test_pure_noise_is_usually_not_significant(self):
        verdicts = [analyze(self.make(0.0, 1.0, seed=s)).verdict for s in range(40)]
        self.assertGreaterEqual(verdicts.count("not significant"), 34)

    def test_ci_matches_t_test(self):
        for seed in range(30):
            r = analyze(self.make(0.01, 0.5, seed=seed))
            ci_excludes_zero = r.ci_low > 0 or r.ci_high < 0
            self.assertEqual(ci_excludes_zero, r.p_linear < 0.05)

    def test_confidence_band_contains_fit(self):
        df = self.make(0.03, 0.4)
        r = analyze(df)
        years, lo, hi = confidence_band(df, r)
        fit = r.intercept + r.slope * years
        self.assertTrue(np.all(lo < fit) and np.all(fit < hi))

    def test_too_short(self):
        with self.assertRaises(ValueError):
            analyze(self.make(0.1, 0.1, n=4))

    def test_years_needed_shrinks_with_bigger_slope(self):
        a = years_needed_for_significance(0.01, 0.5)
        b = years_needed_for_significance(0.05, 0.5)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertLess(b, a)
        self.assertIsNone(years_needed_for_significance(0.0, 0.5))

    def test_years_needed_consistent_with_t_test(self):
        n = years_needed_for_significance(0.02, 0.4)
        se = 0.4 / math.sqrt(n * (n * n - 1) / 12)
        self.assertGreaterEqual(0.02 / se, stats.t.ppf(0.975, n - 2))
        m = n - 1
        se_prev = 0.4 / math.sqrt(m * (m * m - 1) / 12)
        self.assertLess(0.02 / se_prev, stats.t.ppf(0.975, m - 2))

    def test_grid_trends(self):
        rows = []
        for lat, slope in ((45.0, 0.05), (46.0, -0.05)):
            for y in range(1981, 2026):
                rows.append((lat, 100.0, y, slope * (y - 1981) + 0.01 * ((y * 7) % 5)))
        g = pd.DataFrame(rows, columns=["Lat", "Lon", "Year", "Value"])
        t = grid_trends(g, 1981, 2025).set_index("Lat")
        self.assertAlmostEqual(t.loc[45.0, "PerDecade"], 0.5, places=1)
        self.assertAlmostEqual(t.loc[46.0, "PerDecade"], -0.5, places=1)
        self.assertTrue((t["PMK"] < 0.05).all())


class DataTests(unittest.TestCase):
    def test_parse_drops_fill_values(self):
        payload = {"properties": {"parameter": {"T2M": {"198101": -10.0, "198102": -999.0, "198113": -1.5}}}}
        df = parse_point_payload(payload)
        self.assertEqual(len(df), 2)
        self.assertEqual(set(df["Month"]), {1, 13})

    def monthly_frame(self, var, func):
        rows = []
        for y in range(1981, 1986):
            for m in range(1, 14):
                rows.append((var, y, m, func(y, m)))
        return pd.DataFrame(rows, columns=["Variable", "Year", "Month", "Value"])

    def test_whole_year_uses_power_annual_value(self):
        df = self.monthly_frame("T2M", lambda y, m: 99.0 if m == 13 else float(m))
        s = seasonal_series(df, "T2M", "Whole year")
        self.assertTrue((s["Value"] == 99.0).all())
        self.assertEqual(len(s), 5)

    def test_winter_spans_year_boundary(self):
        # value encodes year*100 + month so we can check which months were used
        df = self.monthly_frame("T2M", lambda y, m: y * 100 + m)
        s = seasonal_series(df, "T2M", "Winter (Dec-Feb)").set_index("Year")["Value"]
        self.assertNotIn(1981, s.index)  # Dec 1980 missing
        self.assertAlmostEqual(s[1982], (198112 + 198201 + 198202) / 3, places=3)  # values rounded to 4 dp
        self.assertNotIn(1986, s.index)  # Jan/Feb 1986 missing

    def test_sum_aggregation_for_frost_days(self):
        df = self.monthly_frame("FROST_DAYS", lambda y, m: 10.0)
        s = seasonal_series(df, "FROST_DAYS", "Spring (Mar-May)")
        self.assertTrue((s["Value"] == 30.0).all())

    def test_point_in_polygon_with_hole(self):
        square = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        hole = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
        lons = np.array([5, 2, 11, 5, -1])
        lats = np.array([5, 2, 5, 9, 5])
        inside = points_in_polygons(lons, lats, [[square, hole]])
        self.assertEqual(inside.tolist(), [False, True, False, True, False])


class CatalogTests(unittest.TestCase):
    def test_variables_complete(self):
        for key, meta in VARIABLES.items():
            for field in ("label", "unit", "raw_unit", "theme", "agg", "definition", "why", "source", "palette"):
                self.assertIn(field, meta, f"{key} missing {field}")
            self.assertIn(meta["agg"], ("mean", "max", "min", "sum"))

    def test_map_variables_known(self):
        self.assertTrue(set(MAP_VARIABLES) <= set(VARIABLES))
        self.assertIsNone(SEASONS["Whole year"])


if __name__ == "__main__":
    unittest.main()
