"""Download the NASA POWER snapshot that ships with the app.

Saves:
  data/bundled/points/<location>.json      raw POWER monthly responses for every preset location
  data/bundled/mongolia_grid_annual.csv.gz  annual values on the native POWER grid over Mongolia

The app works without these files (it fetches live), but bundling them makes the demo
instant and reliable on slow Wi-Fi. Re-run any time to refresh:

    python3 scripts/build_bundled_data.py            # everything
    python3 scripts/build_bundled_data.py points     # preset locations only
    python3 scripts/build_bundled_data.py grid       # Mongolia grid only

AI disclosure: written with help from Claude Code (Anthropic's AI coding assistant). See README, "Use of AI".
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trend_detective.catalog import (  # noqa: E402
    END_YEAR,
    LOCATIONS,
    MAP_VARIABLES,
    MONGOLIA_BOXES,
    START_YEAR,
    VARIABLES,
)
from trend_detective.data import (  # noqa: E402
    GRID_FILE,
    POINT_BUNDLE_DIR,
    bundle_path_for,
    fetch_point_payload,
    fetch_regional_payload,
    payload_units,
)


def with_retries(fn, *args, attempts: int = 4, **kwargs):
    for i in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if i == attempts - 1:
                raise
            wait = 5 * (i + 1)
            print(f"   retry in {wait}s after: {exc}")
            time.sleep(wait)


def build_points() -> None:
    POINT_BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    for name, (lat, lon, _desc) in LOCATIONS.items():
        print(f"[points] {name} ({lat}, {lon})")
        payload = with_retries(fetch_point_payload, lat, lon, list(VARIABLES))
        units = payload_units(payload)
        for var, meta in VARIABLES.items():
            if units.get(var) != meta["raw_unit"]:
                raise SystemExit(f"Unit mismatch for {var}: API says {units.get(var)!r}, catalog expects {meta['raw_unit']!r}")
        payload["_bundle"] = {"downloaded": today, "location": name}
        bundle_path_for(name).write_text(json.dumps(payload, separators=(",", ":")))
        time.sleep(1)


def build_grid() -> None:
    years = [str(y) for y in range(START_YEAR, END_YEAR + 1)]
    rows: dict[tuple[str, float, float], dict] = {}
    for var in MAP_VARIABLES:
        for box in MONGOLIA_BOXES:
            t0 = time.time()
            payload = with_retries(fetch_regional_payload, var, box)
            n = 0
            for feat in payload["features"]:
                lon, lat = feat["geometry"]["coordinates"][:2]
                series = feat["properties"]["parameter"][var]
                key = (var, round(lat, 4), round(lon, 4))
                if key in rows:
                    continue
                row = {"Variable": var, "Lat": round(lat, 4), "Lon": round(lon, 4)}
                for y in years:
                    v = series.get(f"{y}13")
                    row[y] = None if v is None or float(v) == -999.0 else round(float(v), 3)
                rows[key] = row
                n += 1
            print(f"[grid] {var} box {box}: {n} new cells in {time.time() - t0:.1f}s")
            time.sleep(1)
    df = pd.DataFrame(list(rows.values()))
    GRID_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(GRID_FILE, index=False, compression="gzip")
    print(f"[grid] wrote {len(df)} rows to {GRID_FILE} ({GRID_FILE.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "points"):
        build_points()
    if what in ("all", "grid"):
        build_grid()
    print("done")
