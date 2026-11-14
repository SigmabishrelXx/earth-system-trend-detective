"""Build the scrolling project website (docs/index.html) for GitHub Pages.

    python3 scripts/build_site.py                          # without a live app link
    python3 scripts/build_site.py --app-url https://...    # with the live app (mission cards link into it)

A one-page, scroll-driven showcase: hero with a tilting app preview, the challenge, why Mongolia (sourced facts),
who the tool is for, a sticky "how it works" walkthrough, live interactive charts (map, scanner, temperature
stripes timeline, seasons), example missions and the conclusion. Charts are made by trend_detective.figures
from the bundled NASA POWER data (light style). The 7-slide demo lives at docs/slides/.

AI disclosure: written with help from Claude Code (Anthropic's AI coding assistant). See README, "Use of AI".
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

import plotly

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_web_slides import MAP_VARS, REPO, PDF_URL, build_data  # noqa: E402
from trend_detective import catalog as C  # noqa: E402
from trend_detective.analysis import format_p  # noqa: E402
from trend_detective.figures import site_style  # noqa: E402
from scipy import stats as sstats  # noqa: E402
from trend_detective.analysis import analyze  # noqa: E402
from trend_detective.data import country_average, load_grid, load_point, seasonal_series, source_consistent  # noqa: E402

SEASON_WORD = {"Whole year": "", "Winter (Dec-Feb)": "winter", "Spring (Mar-May)": "spring",
               "Summer (Jun-Aug)": "summer", "Autumn (Sep-Nov)": "autumn"}


def _pack(df, trimmed: bool) -> dict:
    """Everything the in-browser demo needs for one series, computed with the app's own statistics code."""
    r = analyze(df)
    years = [int(y) for y in df["Year"]]
    out = {"v": [round(float(x), 4) for x in df["Value"]], "s": r.slope, "b": r.intercept, "rs": r.resid_std,
           "tc": float(sstats.t.ppf(0.975, r.n - 2)), "pd": r.per_decade, "tot": r.total_change, "mk": r.mk.p,
           "tp": r.p_linear, "r2": r.r2, "vd": {"significant": "s", "mixed": "m", "not significant": "n"}[r.verdict],
           "yn": r.years_needed, "tr": int(trimmed), "lag": int(r.lag1 > 0.3)}
    if years == list(range(years[0], years[0] + len(years))):
        out["y0"] = years[0]
    else:
        out["y"] = years
    for k in ("s", "b", "rs", "tc", "pd", "tot", "r2"):
        out[k] = round(out[k], 6)
    out["mk"], out["tp"] = float(f"{out['mk']:.4g}"), float(f"{out['tp']:.4g}")
    return out


def build_demo() -> dict:
    grid = load_grid()
    locs = [{"id": "MNG", "name": "All of Mongolia (average)", "short": "Mongolia (country average)", "region": 1}]
    locs += [{"id": C.slugify(n), "name": n, "short": n, "region": 0} for n in C.LOCATIONS]
    series = {}
    for var in C.MAP_VARIABLES:
        df = country_average(grid, var)
        df, trimmed = source_consistent(var, df)
        series[f"MNG|{var}|Whole year"] = _pack(df, trimmed)
    for name, (lat, lon, _) in C.LOCATIONS.items():
        monthly, _ = load_point(lat, lon)
        for var in C.VARIABLES:
            for season in C.SEASONS:
                df, trimmed = source_consistent(var, seasonal_series(monthly, var, season))
                if len(df) >= 5 and df["Value"].std() > 0:
                    series[f"{C.slugify(name)}|{var}|{season}"] = _pack(df, trimmed)
    vars_ = [{"id": k, "label": m["label"], "unit": m["unit"], "theme": m["theme"], "def": m["definition"]} for k, m in C.VARIABLES.items()]
    return {"locs": locs, "vars": vars_, "seasons": list(C.SEASONS), "word": SEASON_WORD, "series": series}


ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SLIDES_URL = "slides/"

# Mongolia context. Every number has a source shown on the page.
FACTS = [
    {"n": 3.5, "dec": 1, "suffix": " million", "label": "people live in Mongolia",
     "src": "National Statistics Office of Mongolia, Dec 2024 (via CEIC)", "url": "https://www.ceicdata.com/en/indicator/mongolia/population"},
    {"n": 64.7, "dec": 1, "suffix": " million", "label": "livestock animals at the end of 2023",
     "src": "Mongolia Dzud Response Plan 2024 (UN OCHA)", "url": "https://humanitarianaction.info/plan/1197/article/mongolia-dzud-response-plan-2024"},
    {"n": 8.1, "dec": 1, "suffix": " million", "label": "animals died in the 2023-24 dzud: 12.5% of all livestock",
     "src": "Ministry of Food, Agriculture and Light Industry, via IFRC final report (ReliefWeb)", "url": "https://reliefweb.int/report/mongolia/final-report-mongolia-cold-wave-dzud-mdrmn020"},
    {"n": 90, "dec": 0, "suffix": "%", "label": "of the country was hit by that dzud (March 2024)",
     "src": "UN Mongolia / UNICEF situation reports (ReliefWeb)", "url": "https://reliefweb.int/report/mongolia/unicef-mongolia-humanitarian-situation-report-no-3-dzud-22-march-2024"},
]

USERS = [
    {"id": "school", "icon": "🎒", "name": "High-school students", "who": "Ages 14-18, science and geography classes",
     "q": "Is my city really getting warmer?",
     "how": ["Pick a guided mission, like “Is Mongolia warming?”", "Guess first: up, down or no trend", "Read a plain-language verdict and see why"],
     "mission": 1},
    {"id": "uni", "icon": "🎓", "name": "University students", "who": "Ages 18-24, environmental science, statistics, geography",
     "q": "Is this trend statistically significant?",
     "how": ["Test any variable at any point on Earth", "Compare the t-test, 95% confidence interval, Mann-Kendall test and Sen's slope", "Download the data as CSV for their own analysis"],
     "mission": 6},
    {"id": "teacher", "icon": "🧑‍🏫", "name": "Teachers", "who": "Secondary schools and universities",
     "q": "How do I teach climate data in one lesson?",
     "how": ["Share a ready-made mission link (…/?mission=3)", "Let students predict, then reveal the evidence", "Use the Learn tab's simple definitions"],
     "mission": 3},
    {"id": "herder", "icon": "🐑", "name": "Herders and rural communities", "who": "Today through English-speaking extension workers, NGO staff and soum officials",
     "q": "Are winters, snow and pasture changing where we graze?",
     "how": ["Click their area on the map of Mongolia", "Check soil moisture, snow depth and frost days", "See the trend by season, not just by year"],
     "mission": 4, "note": "Next: a Mongolian-language version, so herders can use it directly."},
    {"id": "public", "icon": "📰", "name": "Journalists and curious citizens", "who": "Anyone with a basic science background",
     "q": "Is that headline about the climate true?",
     "how": ["Look at the whole-country average", "Compare two places side by side", "Read the honest warnings about data limits"],
     "mission": 5},
]

STEPS = [
    {"t": "Choose what to investigate", "d": "14 NASA variables in three themes: temperature; water; and air & energy. Each one has a simple definition and a note on why it matters. Or start with one of six guided missions.", "img": "app.png"},
    {"t": "Choose where", "d": "Any point on Earth, five Mongolian regions, or all of Mongolia averaged from 587 grid cells. Click any cell on the map to see its own story.", "img": "map.png"},
    {"t": "Choose when", "d": "The whole year or one season, any years from 1981 to 2025. Seasons often tell different stories: Mongolian summers warm while winters don't.", "img": "seasons.png"},
    {"t": "Get a verdict, with its uncertainty shown", "d": "A t-test with a 95% confidence interval, the Mann-Kendall test and Sen's slope. The app calls a trend significant only when both tests agree, explains it in plain words, and flags its limits: data-source changes, correlated years and testing many things at once.", "img": "investigate.png"},
]

MISSIONS = [
    ("Is Mongolia warming?", "Start big: the average temperature of the whole country."),
    ("Summer vs winter in Ulaanbaatar", "A yearly average can hide what each season is doing."),
    ("Svalbard vs Ulaanbaatar winters", "Opposite trends in two places: test a debated idea instead of assuming it."),
    ("Taiga vs Gobi: where is the soil drying?", "Root-zone soil moisture at Lake Khuvsgul versus the South Gobi."),
    ("Are Gobi winds slowing down?", "The wind that lifts dust storms, tested for a trend."),
    ("Fewer frost days on the steppe?", "And why a shorter record can hide a real trend."),
]

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Earth System Trend Detective · NASA Space Apps 2026 · Team Florensiza</title>
<meta name="description" content="Find out what is changing in Earth's climate, where, by how much, and whether it is statistically significant. NASA POWER data, Mongolia focus. NASA Space Apps Challenge 2026, Team Florensiza (Bishrel), Ulaanbaatar.">
<meta name="author" content="Bishrel (Team Florensiza)">
<meta property="og:title" content="Earth System Trend Detective · NASA Space Apps 2026">
<meta property="og:description" content="Is Mongolia's climate really changing? Find out what is changing, where, how much, and whether it is significant, with NASA data.">
<meta property="og:image" content="https://sigmabishrelxx.github.io/earth-system-trend-detective/img/og.png">
<meta property="og:url" content="https://sigmabishrelxx.github.io/earth-system-trend-detective/">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Ctext y=%22.9em%22 font-size=%2290%22%3E%F0%9F%94%8E%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,500..900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="plotly.min.js" defer></script>
<style>
  :root { --bg:#f6f8fb; --card:#ffffff; --ink:#0b1220; --muted:#5b6678; --line:#e3e8f0; --navy:#0b2545; --navy2:#13396b;
          --hot:#e8552f; --hot2:#ff7a52; --cool:#2563eb; --teal:#0f9f8f; --ease:cubic-bezier(.16,1,.3,1);
          --display:"Archivo","Helvetica Neue",Arial,sans-serif; --body:"Inter",-apple-system,"Helvetica Neue",Arial,sans-serif; }
  * { box-sizing:border-box; margin:0; padding:0; }
  html { scroll-behavior:smooth; scroll-padding-top:84px; }
  body { font-family:var(--body); color:var(--ink); background:
         radial-gradient(1200px 700px at 85% -10%, rgba(232,85,47,.10), transparent 60%),
         radial-gradient(1000px 600px at -10% 20%, rgba(37,99,235,.07), transparent 60%), var(--bg); line-height:1.55; }
  a { color:inherit; }
  .wrap { max-width:1200px; margin:0 auto; padding:0 28px; }
  section { padding:110px 0; position:relative; }
  h1, h2, h3 { font-family:var(--display); letter-spacing:-.01em; line-height:1.05; }
  h1 { font-size:clamp(44px, 6.6vw, 92px); font-weight:850; font-stretch:105%; }
  h2 { font-size:clamp(34px, 4.4vw, 58px); font-weight:820; font-stretch:105%; }
  h3 { font-size:24px; font-weight:750; }
  .hl { color:var(--hot); }
  .kicker { display:inline-block; font-size:13px; letter-spacing:.22em; text-transform:uppercase; font-weight:700; color:var(--hot); margin-bottom:16px; }
  .lead { font-size:clamp(18px, 1.6vw, 21px); color:var(--muted); max-width:760px; }
  .center { text-align:center; } .center .lead { margin:0 auto; }
  .muted { color:var(--muted); }

  /* nav */
  header { position:fixed; top:0; left:0; right:0; z-index:50; transition:background .3s, box-shadow .3s, backdrop-filter .3s; }
  header.scrolled { background:rgba(246,248,251,.82); backdrop-filter:blur(14px); box-shadow:0 1px 0 var(--line); }
  .nav { display:flex; align-items:center; gap:28px; height:72px; }
  .logo { font-family:var(--display); font-stretch:125%; font-weight:900; font-size:15px; line-height:1; text-transform:uppercase; text-decoration:none; letter-spacing:.01em; }
  .logo span { color:var(--hot); }
  .nav nav { display:flex; gap:24px; margin-left:auto; }
  .nav nav a { text-decoration:none; font-size:15px; font-weight:500; color:var(--ink); opacity:.78; transition:opacity .2s; position:relative; }
  .nav nav a:hover, .nav nav a.on { opacity:1; }
  .nav nav a.on::after { content:""; position:absolute; left:0; right:0; bottom:-6px; height:2px; background:var(--hot); border-radius:2px; }
  .btn { display:inline-flex; align-items:center; gap:12px; text-decoration:none; font-weight:650; border-radius:12px; cursor:pointer; border:none; font-family:var(--body); }
  .btn-primary { background:linear-gradient(180deg, var(--navy2), var(--navy)); color:#fff; padding:6px 6px 6px 22px; font-size:17px;
                 box-shadow:0 10px 30px rgba(11,37,69,.25); transition:transform .2s var(--ease), box-shadow .2s; }
  .btn-primary:hover { transform:translateY(-2px); box-shadow:0 16px 40px rgba(11,37,69,.32); }
  .btn-primary .arr { width:40px; height:40px; border-radius:9px; background:var(--hot); display:grid; place-items:center; font-size:20px; }
  .btn-ghost { padding:14px 22px; font-size:17px; color:var(--navy); background:#fff; border:1px solid var(--line); }
  .btn-ghost:hover { border-color:#c9d3e2; }
  .btn-sm { padding:4px 4px 4px 16px; font-size:14px; } .btn-sm .arr { width:32px; height:32px; font-size:16px; }
  .burger { display:none; }

  /* hero */
  .hero { padding:150px 0 40px; text-align:center; }
  .pill { display:inline-flex; gap:8px; align-items:center; padding:7px 14px; border-radius:999px; background:#fff; border:1px solid var(--line);
          font-size:14px; color:var(--muted); margin-bottom:26px; }
  .pill b { color:var(--ink); }
  .hero .lead { margin:26px auto 0; }
  .hero .ctas { display:flex; gap:14px; justify-content:center; flex-wrap:wrap; margin-top:36px; }
  .frame-wrap { perspective:1600px; margin:70px auto 0; max-width:1180px; }
  .frame { border-radius:20px; padding:0; background:transparent; transform-origin:center top; will-change:transform; }
  .demo { display:grid; grid-template-columns:330px 1fr; text-align:left; background:#0b0f17; color:#e8edf5; border-radius:20px; overflow:hidden;
          box-shadow:0 40px 100px rgba(11,37,69,.22), 0 0 0 1px rgba(15,23,42,.08); transform-origin:center top; will-change:transform; }
  .demo-side { background:#121826; padding:26px 22px; border-right:1px solid #243045; display:flex; flex-direction:column; }
  .demo-brand { font-family:var(--display); font-weight:850; font-size:17px; margin-bottom:22px; }
  .demo-brand span { font-family:var(--body); font-size:11px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:#ff8a70;
                     border:1px solid rgba(255,107,74,.4); border-radius:999px; padding:3px 8px; margin-top:8px; display:table; white-space:nowrap; }
  .demo-side label { display:block; font-size:13px; color:#93a1b8; margin-bottom:14px; font-weight:500; }
  .demo-side select { width:100%; margin-top:6px; background:#0b0f17; color:#e8edf5; border:1px solid #2b3850; border-radius:10px; padding:10px 34px 10px 12px;
                      font:500 14px var(--body); appearance:none; -webkit-appearance:none; cursor:pointer;
                      background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%2393a1b8' stroke-width='1.8' fill='none'/%3E%3C/svg%3E");
                      background-repeat:no-repeat; background-position:right 12px center; }
  .demo-side select:disabled { opacity:.55; cursor:not-allowed; }
  .demo-side select:focus { outline:2px solid rgba(255,107,74,.6); outline-offset:1px; }
  .demo-def { font-size:13px; color:#93a1b8; line-height:1.5; margin-top:4px; }
  .demo-cta { margin-top:auto; padding-top:18px; font-size:13px; color:#93a1b8; }
  .demo-cta a { color:#ff8a70; font-weight:700; text-decoration:none; }
  .demo-main { padding:22px 28px 18px; min-width:0; }
  .demo-top { font-size:12.5px; color:#93a1b8; margin-bottom:10px; } .demo-top .live { color:#34d399; font-weight:700; margin-right:6px; }
  .demo-main h3 { font-family:var(--display); font-size:24px; color:#fff; margin-bottom:14px; }
  .demo-metrics { display:grid; grid-template-columns:repeat(5, 1fr); gap:10px; }
  .demo-metrics .m { background:rgba(148,163,184,.07); border:1px solid rgba(148,163,184,.18); border-radius:12px; padding:10px 12px; min-width:0; }
  .demo-metrics .k { font-size:11.5px; color:#93a1b8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .demo-metrics .v { font-size:21px; font-weight:600; margin-top:4px; white-space:nowrap; }
  .demo-verdict { margin:12px 0 4px; padding:12px 14px; border-radius:12px; font-size:14px; line-height:1.5; }
  .demo-verdict.ok { background:rgba(16,185,129,.12); color:#a7f3d0; } .demo-verdict.warn { background:rgba(245,158,11,.12); color:#fde68a; }
  .demo-verdict.info { background:rgba(59,130,246,.13); color:#bfdbfe; } .demo-verdict b { color:#fff; }
  .demo-note { font-size:12.5px; color:#93a1b8; min-height:16px; }
  @media (max-width: 960px) { .demo { grid-template-columns:1fr; } .demo-side { border-right:none; border-bottom:1px solid #243045; }
    .demo-metrics { grid-template-columns:repeat(3, 1fr); } }
  @media (max-width: 560px) { .demo-metrics { grid-template-columns:repeat(2, 1fr); } .demo-main { padding:18px; } }
  .frame img { display:block; width:100%; border-radius:20px; box-shadow:0 40px 100px rgba(11,37,69,.20), 0 0 0 1px rgba(15,23,42,.06); }
  .ribbon { display:flex; height:16px; border-radius:8px; overflow:hidden; margin:34px auto 0; max-width:1180px; }
  .ribbon i { flex:1; }
  .ribbon-cap { font-size:13px; color:var(--muted); margin-top:10px; }

  /* reveal on scroll */
  .rv { opacity:0; transform:translateY(34px); transition:opacity .9s var(--ease), transform .9s var(--ease); transition-delay:calc(var(--d,0) * 1ms); }
  .rv.in { opacity:1; transform:none; }

  /* cards */
  .grid4 { display:grid; grid-template-columns:repeat(4, 1fr); gap:20px; margin-top:48px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:26px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
  .card .ico { width:46px; height:46px; border-radius:12px; display:grid; place-items:center; font-size:22px; background:#fff1ec; margin-bottom:16px; }
  .card p { color:var(--muted); font-size:16px; margin-top:8px; }
  .two { display:grid; grid-template-columns:1fr 1fr; gap:60px; align-items:center; }

  /* why mongolia */
  .why { background:linear-gradient(180deg, #0b2545, #0d1d36); color:#e8edf5; border-radius:36px; margin:0 20px; padding:100px 0; }
  .why .lead { color:#a9b6cc; }
  .stats { display:grid; grid-template-columns:repeat(4, 1fr); gap:22px; margin-top:54px; }
  .stat { border-top:2px solid rgba(255,255,255,.14); padding-top:22px; }
  .stat .n { font-family:var(--display); font-stretch:115%; font-weight:900; font-size:clamp(40px, 4vw, 58px); line-height:1; color:#fff; }
  .stat .n.hot { color:var(--hot2); }
  .stat .l { margin-top:10px; font-size:17px; color:#c8d2e3; }
  .stat .s { margin-top:12px; font-size:12px; color:#7f8ea8; } .stat .s a { color:#9fb3d4; }

  /* users */
  .users { display:grid; grid-template-columns:340px 1fr; gap:28px; margin-top:48px; align-items:start; }
  .ulist { display:flex; flex-direction:column; gap:10px; }
  .ubtn { display:flex; gap:14px; align-items:center; text-align:left; padding:16px 18px; border-radius:16px; border:1px solid var(--line); background:#fff;
          cursor:pointer; font-family:var(--body); font-size:16px; color:var(--ink); transition:all .25s var(--ease); }
  .ubtn .e { font-size:24px; } .ubtn small { display:block; color:var(--muted); font-size:13px; margin-top:2px; }
  .ubtn:hover { border-color:#c9d3e2; transform:translateX(4px); }
  .ubtn.on { border-color:var(--hot); box-shadow:0 10px 30px rgba(232,85,47,.12); }
  .upanel { background:#fff; border:1px solid var(--line); border-radius:24px; padding:38px; min-height:420px; position:relative; overflow:hidden; }
  .upanel .big { font-size:64px; line-height:1; }
  .upanel blockquote { font-family:var(--display); font-stretch:105%; font-size:clamp(24px, 2.4vw, 34px); font-weight:780; margin:18px 0 6px; line-height:1.15; }
  .upanel ol { margin:22px 0 0 0; list-style:none; counter-reset:s; }
  .upanel ol li { counter-increment:s; padding-left:46px; position:relative; margin-bottom:14px; font-size:17px; }
  .upanel ol li::before { content:counter(s); position:absolute; left:0; top:-2px; width:30px; height:30px; border-radius:50%; background:var(--navy); color:#fff;
                          display:grid; place-items:center; font-size:14px; font-weight:700; }
  .upanel .note { margin-top:16px; font-size:14px; color:var(--teal); font-weight:600; }
  .upanel .fade { animation:pfade .5s var(--ease); }
  @keyframes pfade { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:none; } }

  /* how it works: sticky scrollytelling */
  .how { display:grid; grid-template-columns:1fr 1.15fr; gap:60px; margin-top:40px; }
  .steps .step { min-height:70vh; display:flex; flex-direction:column; justify-content:center; padding:20px 0; opacity:.35; transition:opacity .4s; }
  .steps .step.on { opacity:1; }
  .steps .step .no { font-family:var(--display); font-weight:900; font-size:15px; color:var(--hot); letter-spacing:.14em; margin-bottom:12px; }
  .steps .step h3 { font-size:clamp(26px, 2.6vw, 36px); }
  .steps .step p { color:var(--muted); font-size:18px; margin-top:14px; max-width:460px; }
  .sticky { position:sticky; top:110px; height:calc(100vh - 160px); display:flex; align-items:center; }
  .shots { position:relative; width:100%; aspect-ratio:16/11; background:transparent; }
  .shots img { position:absolute; inset:0; margin:auto; max-width:100%; max-height:100%; width:auto; height:auto; border-radius:18px;
               box-shadow:0 30px 80px rgba(11,37,69,.20), 0 0 0 1px rgba(15,23,42,.06); opacity:0; transform:scale(1.04);
               transition:opacity .6s var(--ease), transform .8s var(--ease); }
  .shots img.on { opacity:1; transform:none; }
  .dots { position:absolute; left:50%; transform:translateX(-50%); bottom:-28px; display:flex; gap:6px; z-index:2; }
  .dots i { width:8px; height:8px; border-radius:50%; background:rgba(15,23,42,.18); transition:all .3s; }
  .dots i.on { background:var(--hot2); width:22px; border-radius:5px; }

  /* explore */
  .panel { background:#fff; border:1px solid var(--line); border-radius:24px; padding:24px; }
  .explore { display:grid; grid-template-columns:1.35fr 1fr; gap:22px; margin-top:44px; align-items:start; }
  .chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
  .chip { font-family:var(--body); font-size:14px; padding:7px 14px; border-radius:999px; border:1px solid var(--line); background:#fff; color:var(--muted); cursor:pointer; transition:all .15s; }
  .chip:hover { color:var(--ink); border-color:#c9d3e2; } .chip.on { background:var(--navy); color:#fff; border-color:var(--navy); }
  .cap { font-size:14px; color:var(--muted); margin-top:8px; }
  table.scan { width:100%; border-collapse:collapse; font-size:15px; }
  table.scan td, table.scan th { padding:9px 8px; border-bottom:1px solid var(--line); text-align:left; }
  table.scan th { font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); font-weight:600; }
  table.scan td.r, table.scan th.r { text-align:right; white-space:nowrap; }
  table.scan tr.mixed td, table.scan tr.not-significant td { color:var(--muted); }

  /* findings: stripes timeline */
  .tl { position:relative; margin-top:60px; }
  .tl .bar { display:flex; height:180px; border-radius:16px; overflow:hidden; cursor:crosshair; box-shadow:0 30px 70px rgba(11,37,69,.18); }
  .tl .bar i { flex:1; transition:transform .25s; } .tl .bar i:hover { transform:scaleY(1.06); }
  .tl .yrs { position:relative; height:28px; margin-top:8px; } .tl .yrs span { position:absolute; transform:translateX(-50%); font-size:13px; color:var(--muted); }
  .tl .pins { position:relative; height:70px; } .tl .pin { position:absolute; bottom:0; transform:translateX(-50%); text-align:center; opacity:0; transition:opacity .6s; }
  .tl .pin .t { font-size:13px; color:var(--muted); white-space:nowrap; } .tl .pin .v { font-family:var(--display); font-weight:850; font-size:20px; }
  .tl .pin .stem { width:2px; height:16px; background:var(--ink); opacity:.5; margin:4px auto 0; }
  .tl .pin .v, .tl .pin .t { white-space:nowrap; }
  .tl .pin:last-child { transform:translateX(-82%); text-align:right; } .tl .pin:last-child .stem { margin-right:16%; }
  .tl .pin:first-child { transform:translateX(-20%); text-align:left; } .tl .pin:first-child .stem { margin-left:18%; }
  .tl .scanline { position:absolute; top:70px; height:180px; width:3px; background:#fff; box-shadow:0 0 16px 3px rgba(255,255,255,.9); opacity:0; pointer-events:none; }
  .tl .readout { position:absolute; top:28px; transform:translateX(-50%); font-family:var(--display); font-weight:850; font-size:22px; opacity:0; pointer-events:none; white-space:nowrap; }
  .tip { position:fixed; z-index:60; pointer-events:none; background:#0b1220; color:#fff; padding:6px 12px; border-radius:9px; font-size:14px; opacity:0; transition:opacity .15s; }
  .bigstats { display:grid; grid-template-columns:repeat(3, 1fr); gap:22px; margin-top:44px; }
  .bigstats .card .n { font-family:var(--display); font-stretch:112%; font-weight:900; font-size:clamp(36px, 3.7vw, 54px); line-height:1; white-space:nowrap; }
  .twist { display:grid; grid-template-columns:0.8fr 1.4fr; gap:36px; margin-top:80px; align-items:start; }
  .twist p { font-size:19px; margin-bottom:16px; }

  /* missions */
  .missions { display:grid; grid-template-columns:repeat(3, 1fr); gap:18px; margin-top:44px; }
  .mcard { background:#fff; border:1px solid var(--line); border-radius:20px; padding:24px; text-decoration:none; display:block; transition:all .25s var(--ease); }
  .mcard:hover { transform:translateY(-4px); box-shadow:0 20px 50px rgba(11,37,69,.12); border-color:#c9d3e2; }
  .mcard .no { font-family:var(--display); font-weight:900; color:var(--hot); font-size:14px; letter-spacing:.12em; }
  .mcard h3 { margin-top:10px; font-size:21px; } .mcard p { color:var(--muted); font-size:15px; margin-top:8px; }
  .mcard .go { margin-top:16px; font-size:14px; font-weight:650; color:var(--navy2); }

  /* conclusion + footer */
  .final { background:linear-gradient(160deg, #0b2545, #13396b 60%, #1d5a9b); color:#fff; border-radius:36px; margin:0 20px; padding:90px 0; overflow:hidden; position:relative; }
  .final .lead { color:#c8d6ec; }
  .final ul { list-style:none; margin-top:28px; } .final li { padding-left:30px; position:relative; margin-bottom:12px; font-size:18px; color:#dfe7f4; }
  .final li::before { content:"→"; position:absolute; left:0; color:var(--hot2); font-weight:800; }
  .final .links { display:flex; gap:12px; flex-wrap:wrap; margin-top:34px; }
  .final .btn-ghost { background:rgba(255,255,255,.1); color:#fff; border-color:rgba(255,255,255,.25); }
  footer { padding:50px 0 70px; font-size:13px; color:var(--muted); }
  footer p { margin-bottom:8px; max-width:1000px; }

  @media (max-width: 960px) {
    .nav nav { display:none; } .two, .users, .how, .explore, .twist { grid-template-columns:1fr; } .grid4, .stats { grid-template-columns:1fr 1fr; }
    .bigstats, .missions { grid-template-columns:1fr; } .sticky { position:relative; top:0; height:auto; } .steps .step { min-height:auto; opacity:1; }
    .how .sticky { order:-1; } section { padding:80px 0; } .why, .final { margin:0 10px; }
  }
  @media (max-width: 560px) { .grid4, .stats { grid-template-columns:1fr; } .wrap { padding:0 18px; } }
  @media (prefers-reduced-motion: reduce) { .rv { opacity:1; transform:none; transition:none; } html { scroll-behavior:auto; } }
</style>
</head>
<body>
<div class="tip" id="tip"></div>

<header id="top"><div class="wrap nav">
  <a class="logo" href="#top">Earth System<br>Trend <span>Detective</span></a>
  <nav>
    <a href="#about">About</a><a href="#why">Why Mongolia</a><a href="#users">Who it's for</a><a href="#how">How it works</a>
    <a href="#explore">Explore</a><a href="#findings">Findings</a><a href="#conclusion">Conclusion</a>
  </nav>
  __NAV_CTA__
</div></header>

<!-- HERO -->
<section class="hero"><div class="wrap">
  <div class="pill rv">🛰️ NASA Space Apps 2026 · <b>Be An Earth System Trend Detective!</b></div>
  <h1 class="rv" style="--d:80">Is Mongolia's climate<br><span class="hl">really</span> changing?</h1>
  <p class="lead rv" style="--d:160">Earth System Trend Detective turns 45 years of NASA model and satellite data into clear answers:
    <b>what is changing, where, by how much, and whether it is statistically significant.</b></p>
  <div class="ctas rv" style="--d:240">
    __HERO_CTA__
    <a class="btn btn-ghost" href="__SLIDES__">▶ Watch the 7-slide demo</a>
  </div>
  <div class="frame-wrap rv" style="--d:320"><div class="demo" id="frame">
    <aside class="demo-side">
      <div class="demo-brand">🔎 Trend Detective <span>live demo</span></div>
      <label>Location<select id="d-loc"></select></label>
      <label>Earth science variable<select id="d-var"></select></label>
      <label>Season<select id="d-sea"></select></label>
      <p class="demo-def" id="d-def"></p>
      <div class="demo-cta">__DEMO_CTA__</div>
    </aside>
    <div class="demo-main">
      <div class="demo-top"><span class="live">● Live</span> Computed in your browser from NASA POWER data, with the app's own statistics.</div>
      <h3 id="d-title"></h3>
      <div class="demo-metrics" id="d-metrics"></div>
      <div class="demo-verdict" id="d-verdict"></div>
      <div id="d-chart" style="height:300px;"></div>
      <div class="demo-note" id="d-note"></div>
    </div>
  </div></div>
  <div class="ribbon rv" title="Mongolia's yearly temperature, 1981-2025">__RIBBON__</div>
  <div class="ribbon-cap">Each stripe is one year of Mongolia's average temperature, 1981-2025 (blue cooler, red warmer than 1981-2010). NASA POWER / MERRA-2.</div>
</div></section>

<!-- ABOUT -->
<section id="about"><div class="wrap">
  <div class="two">
    <div>
      <span class="kicker rv">About the project</span>
      <h2 class="rv" style="--d:80">A detective tool for Earth's changing climate</h2>
      <p class="lead rv" style="--d:160; margin-top:20px;">NASA's challenge: build a tool that selects Earth science variables, shows how they change over time,
        and works out what is changing, where, how much, and whether the change is significant. We built it for students
        and the public, and tested it on the country we live in.</p>
    </div>
    <div class="rv" style="--d:200">
      <div class="card" style="padding:30px;">
        <p style="margin:0; color:var(--ink); font-size:17px;"><b>Built by Team Florensiza</b> (Bishrel) at the NASA Space Apps Challenge 2026, Ulaanbaatar local event.</p>
        <p style="margin-top:12px;">Python · Streamlit · Plotly · SciPy · NASA POWER API. Open source under the MIT License.</p>
      </div>
    </div>
  </div>
  <div class="grid4">
    <div class="card rv" style="--d:0"><div class="ico">🧭</div><h3>What is changing?</h3><p>A scanner tests 14 variables at once and ranks them by strength of evidence.</p></div>
    <div class="card rv" style="--d:100"><div class="ico">🗺️</div><h3>Where?</h3><p>A trend map of 587 grid cells across Mongolia, plus any point on Earth.</p></div>
    <div class="card rv" style="--d:200"><div class="ico">📈</div><h3>How much?</h3><p>Change per decade and in total, with a 95% confidence band on every chart.</p></div>
    <div class="card rv" style="--d:300"><div class="ico">🧪</div><h3>Is it significant?</h3><p>t-test and Mann-Kendall test. "Significant" only when both agree.</p></div>
  </div>
</div></section>

<!-- WHY MONGOLIA -->
<section id="why" class="why"><div class="wrap">
  <span class="kicker rv">Why Mongolia</span>
  <h2 class="rv" style="--d:80; max-width:900px;">When the climate shifts, herders feel it first</h2>
  <p class="lead rv" style="--d:160; margin-top:20px;">Mongolia's economy and culture depend on livestock grazing open pasture. A dry summer followed by a harsh winter,
    called a <b style="color:#fff">dzud</b>, can wipe out herds. Knowing which changes are real, and where, matters.</p>
  <div class="stats">__STATS__</div>
</div></section>

<!-- USERS -->
<section id="users"><div class="wrap">
  <div class="center">
    <span class="kicker rv">Who it's for</span>
    <h2 class="rv" style="--d:80">Five kinds of trend detectives</h2>
    <p class="lead rv" style="--d:160; margin-top:18px;">The challenge names high-school and college students and members of the public with some science background.
      Here is who we designed for, and what each of them does in the app. Click to explore.</p>
  </div>
  <div class="users">
    <div class="ulist rv" style="--d:200">__USER_BUTTONS__</div>
    <div class="upanel rv" style="--d:300" id="upanel"></div>
  </div>
</div></section>

<!-- HOW IT WORKS -->
<section id="how"><div class="wrap">
  <span class="kicker rv">How it works</span>
  <h2 class="rv" style="--d:80">Four steps from question to verdict</h2>
  <div class="how">
    <div class="steps">__STEPS__</div>
    <div class="sticky"><div class="shots" id="shots">__SHOTS__<div class="dots" id="sdots"></div></div></div>
  </div>
</div></section>

<!-- EXPLORE -->
<section id="explore"><div class="wrap">
  <div class="center">
    <span class="kicker rv">Try it here</span>
    <h2 class="rv" style="--d:80">Be the detective</h2>
    <p class="lead rv" style="--d:160; margin-top:18px;">These are live charts from the app's real NASA data. Hover any grid cell, switch variables, or press play to watch 45 years go by.</p>
  </div>
  <div class="explore">
    <div class="panel rv" style="--d:200">
      <div class="chips" id="map-btns">__MAP_BUTTONS__<button class="chip" data-v="anim">▶ Year by year</button></div>
      <div id="fig-map" style="height:420px;"></div>
      <div class="cap" id="map-caption"></div>
    </div>
    <div class="panel rv" style="--d:320">
      <h3 style="font-size:20px;">What is changing here?</h3>
      <div class="chips" id="scan-btns" style="margin-top:12px;">__SCAN_BUTTONS__</div>
      <p style="font-size:15px; margin-bottom:6px;" id="scan-title"></p>
      <table class="scan"><thead><tr><th></th><th>Variable</th><th class="r">per decade</th><th></th><th class="r">MK p</th><th class="r">t p</th></tr></thead><tbody id="scan-body"></tbody></table>
      <div class="cap">Whole year, 1981-2025, sorted by verdict then Mann-Kendall p. ✅ both tests significant · ⚠️ only one (often a sudden jump or an outlier) · ➖ neither. * Sunlight and cloud cover tested on 2001-2025 only, because their data source changes in 2001.</div>
    </div>
  </div>
</div></section>

<!-- FINDINGS -->
<section id="findings"><div class="wrap">
  <span class="kicker rv">Findings · NASA POWER, 1981-2025</span>
  <h2 class="rv" style="--d:80">Mongolia is warming</h2>
  <p class="lead rv" style="--d:160; margin-top:18px;">Every stripe is one year of the country-average temperature. Hover a stripe for its value.</p>
  <div class="tl rv" style="--d:200" id="tl">
    <div class="pins">__PINS__</div>
    <div class="bar" id="tlbar">__TL_STRIPES__</div>
    <div class="scanline" id="scanline"></div><div class="readout" id="readout"></div>
    <div class="yrs">__TL_YEARS__</div>
  </div>
  <div class="bigstats">
    <div class="card rv" style="--d:0"><div class="n hl" data-count="__T2M_RATE__" data-dec="2" data-prefix="+" data-suffix=" °C">__T2M_RATE_TXT__</div><p>per decade, Mongolia average. Significant (Mann-Kendall p = __T2M_P__).</p></div>
    <div class="card rv" style="--d:120"><div class="n hl" data-count="__WARM__" data-dec="0" data-suffix="%">__WARM__%</div><p>of Mongolia's area warming significantly; __WARM_BH__% after correcting for testing __CELLS__ grid cells at once. __COOL__% cooling.</p></div>
    <div class="card rv" style="--d:240"><div class="n" style="color:var(--teal)" data-count="__WIND_RATE__" data-dec="2" data-suffix=" m/s">__WIND_RATE_TXT__</div><p>per decade: wind is slowing on average across Mongolia (__WIND_VERDICT__), but not everywhere: at Lake Khuvsgul it is rising.</p></div>
  </div>
  <div class="twist">
    <div>
      <span class="kicker rv">The twist</span>
      <h2 class="rv" style="--d:80; font-size:clamp(30px,3.4vw,44px);">…but not evenly</h2>
      <p class="rv" style="--d:160; margin-top:20px;"><b class="hl">Summers</b> warm significantly at __SUMMER_SIG__ of __NSITES__ Mongolian sites.</p>
      <p class="rv" style="--d:220"><b style="color:var(--cool)">Winters</b> lean colder (__WINTER_AVG__ °C per decade), but not significantly.</p>
      <p class="rv" style="--d:280">Meanwhile <b class="hl">Svalbard winters</b> (one Arctic grid point) warm __ARCTIC__ °C per decade: one variable, opposite directions. Whether they are connected ("warm Arctic, cold continent") is a debated idea to test, not proof.</p>
    </div>
    <div class="panel rv" style="--d:200">
      <div class="chips" id="find-btns"><button class="chip on" data-fig="seasons">Seasons at 5 sites</button><button class="chip" data-fig="compare">Svalbard vs Ulaanbaatar winters</button></div>
      <div id="fig-find" style="height:460px;"></div>
      <div class="cap" id="find-caption"></div>
    </div>
  </div>
</div></section>

<!-- MISSIONS -->
<section id="missions"><div class="wrap">
  <div class="center">
    <span class="kicker rv">Example use cases</span>
    <h2 class="rv" style="--d:80">Six guided missions</h2>
    <p class="lead rv" style="--d:160; margin-top:18px;">Each mission sets up the app, asks a question and lets students guess before they see the evidence.
      Teachers can share any of them with a single link.</p>
  </div>
  <div class="missions">__MISSIONS__</div>
</div></section>

<!-- CONCLUSION -->
<section id="conclusion" class="final"><div class="wrap two">
  <div>
    <span class="kicker rv" style="color:var(--hot2)">Conclusion</span>
    <h2 class="rv" style="--d:80">Every student can be a climate trend detective</h2>
    <p class="lead rv" style="--d:160; margin-top:20px;">Real NASA data, honest statistics, and a Mongolian focus, in a free tool anyone can open in a browser.</p>
    <div class="links rv" style="--d:240">__FINAL_CTA__<a class="btn btn-ghost" href="__SLIDES__">▶ 7-slide demo</a><a class="btn btn-ghost" href="__REPO__">Code on GitHub</a></div>
  </div>
  <div class="rv" style="--d:200">
    <h3 style="font-size:22px; color:#fff;">What's next</h3>
    <ul>
      <li>A Mongolian-language version for schools and herder communities</li>
      <li>More NASA data: GLDAS soil water and streamflow, MODIS vegetation greenness</li>
      <li>Seasonal trend maps and more classroom missions</li>
      <li>Trend tests that correct for year-to-year memory</li>
    </ul>
  </div>
</div></section>

<footer><div class="wrap">
  <p><b>Data:</b> "The data was obtained from the National Aeronautics and Space Administration (NASA) Langley Research Center (LaRC) Prediction of
    Worldwide Energy Resource (POWER) Project funded through the NASA Earth Science/Applied Science Program." MERRA-2 (NASA GMAO) and CERES (NASA LaRC) via POWER.
    Mongolia border: Natural Earth (public domain). Stripes style inspired by Ed Hawkins' warming stripes. Mongolia facts: sources under each number above.</p>
  <p><b>Code:</b> started from kdmayer/nasa-power-api (MIT). <b>AI use:</b> the app, this website and the slides were built with help from Claude Code (an AI assistant);
    every number is computed from NASA data by the app's code. NASA does not endorse this project. <a href="__PDF_URL__">PDF slides</a> · <a href="__REPO__">GitHub</a></p>
  <p>© 2026 Team Florensiza · Bishrel · Ulaanbaatar, Mongolia</p>
</div></footer>

<script>
document.addEventListener("DOMContentLoaded", () => {
const FIGS = __FIGS__, FACTS = __FACTS__, SCANS = __SCANS__, STRIPES = __STRIPES_JSON__, USERS = __USERS_JSON__;
const DEMO = __DEMO_JSON__;
const CONFIG = {displaylogo:false, responsive:true, modeBarButtonsToRemove:['lasso2d','select2d','toImage']};
const tip = document.getElementById('tip');

// header + active nav link
const header = document.querySelector('header');
addEventListener('scroll', () => header.classList.toggle('scrolled', scrollY > 20), {passive:true});
const navLinks = [...document.querySelectorAll('.nav nav a')];
const secObs = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) navLinks.forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + e.target.id)); }),
  {rootMargin:'-45% 0px -50% 0px'});
document.querySelectorAll('section[id]').forEach(s => secObs.observe(s));

// reveal on scroll
const rvObs = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); rvObs.unobserve(e.target); } }), {threshold:.12});
document.querySelectorAll('.rv').forEach(el => rvObs.observe(el));

// hero frame tilts flat as you scroll
const frame = document.getElementById('frame');
function frameFx() {
  const r = frame.getBoundingClientRect(), vh = innerHeight;
  const p = Math.min(1, Math.max(0, (vh - r.top) / (vh * 0.75)));
  frame.style.transform = `scale(${0.94 + p * 0.06})`;
}
addEventListener('scroll', () => requestAnimationFrame(frameFx), {passive:true}); frameFx();

// ---------- live demo (a small version of the app, in the browser) ----------
const DM = DEMO;
const fmtNum = (x, unit, signed = true) => { const a = Math.abs(x), d = a >= 1 ? 2 : a >= 0.01 ? 3 : 4;
  const t = (signed && x > 0 ? '+' : '') + x.toFixed(d); return unit ? `${t} ${unit}` : t; };
const fmtP = p => p < 0.0001 ? '< 0.0001' : p < 0.001 ? p.toFixed(4) : p.toFixed(3);
const pText = p => { const s = fmtP(p); return s.startsWith('<') ? `p ${s}` : `p = ${s}`; };
const dLoc = document.getElementById('d-loc'), dVar = document.getElementById('d-var'), dSea = document.getElementById('d-sea');
DM.locs.forEach(l => dLoc.add(new Option(l.name, l.id)));
DM.seasons.forEach(sn => dSea.add(new Option(sn, sn)));
function fillVars() {
  const keep = dVar.value || 'T2M'; dVar.innerHTML = '';
  const loc = dLoc.value, region = DM.locs.find(l => l.id === loc).region;
  const themes = {};
  DM.vars.forEach(v => { const has = DM.seasons.some(sn => DM.series[`${loc}|${v.id}|${sn}`]);
    if (!has) return; (themes[v.theme] = themes[v.theme] || document.createElement('optgroup')).label = v.theme;
    themes[v.theme].appendChild(new Option(`${v.label} (${v.unit === 'fraction' ? 'fraction, 0-1' : v.unit})`, v.id)); });
  Object.values(themes).forEach(g => dVar.appendChild(g));
  dVar.value = [...dVar.options].some(o => o.value === keep) ? keep : 'T2M';
  dSea.disabled = !!region; if (region) dSea.value = 'Whole year';
}
function renderDemo() {
  const loc = DM.locs.find(l => l.id === dLoc.value), v = DM.vars.find(x => x.id === dVar.value), sea = dSea.value;
  const sr = DM.series[`${loc.id}|${v.id}|${sea}`];
  const word = DM.word[sea], what = word ? `${word[0].toUpperCase() + word.slice(1)} ${v.label.toLowerCase()}` : v.label;
  document.getElementById('d-def').textContent = v.def;
  document.getElementById('d-title').textContent = `${what} · ${loc.short}`;
  const mEl = document.getElementById('d-metrics'), vEl = document.getElementById('d-verdict'), nEl = document.getElementById('d-note');
  if (!sr) { mEl.innerHTML = ''; vEl.className = 'demo-verdict info'; vEl.innerHTML = 'No data for this choice (for example, there is no snow in the Amazon). Try another season or variable.';
    Plotly.purge('d-chart'); nEl.textContent = ''; return; }
  const years = sr.y || sr.v.map((_, i) => sr.y0 + i), n = years.length, start = years[0], end = years[n - 1];
  const xm = years.reduce((a, b) => a + b, 0) / n, sxx = years.reduce((a, x) => a + (x - xm) ** 2, 0);
  const fit = years.map(x => sr.b + sr.s * x), half = years.map(x => sr.tc * sr.rs * Math.sqrt(1 / n + (x - xm) ** 2 / sxx));
  const unit = v.unit === 'fraction' ? '' : v.unit;
  mEl.innerHTML = [['Change per decade', fmtNum(sr.pd, unit)], [`Total change (${end - start} yrs)`, fmtNum(sr.tot, unit)],
    ['Mann-Kendall p', fmtP(sr.mk)], ['t-test p', fmtP(sr.tp)], ['R² fit', sr.r2.toFixed(2)]]
    .map(([k, val]) => `<div class="m"><div class="k" title="${k}">${k}</div><div class="v">${val}</div></div>`).join('');
  const dir = sr.s > 0 ? 'increasing' : sr.s < 0 ? 'decreasing' : 'flat', rate = fmtNum(Math.abs(sr.pd), unit, false);
  const tests = `t-test ${pText(sr.tp)}, Mann-Kendall ${pText(sr.mk)}`;
  if (sr.vd === 's') { vEl.className = 'demo-verdict ok';
    vEl.innerHTML = `✅ <b>Significant trend.</b> ${what} at <b>${loc.short}</b> is <b>${dir}</b> by about <b>${rate} per decade</b> (${start}-${end}). Both tests agree (${tests}): a run like this would happen by chance less than 5% of the time.`;
  } else if (sr.vd === 'm') { vEl.className = 'demo-verdict warn';
    const which = sr.tp < 0.05 ? 'The linear t-test' : 'The Mann-Kendall test', other = sr.tp < 0.05 ? 'the Mann-Kendall test' : 'the linear t-test';
    vEl.innerHTML = `⚠️ <b>Possible trend: the tests disagree.</b> ${what} at <b>${loc.short}</b> leans <b>${dir}</b> (about ${rate} per decade, ${start}-${end}). ${which} finds it significant but ${other} does not (${tests}). Treat it as a lead, not proof.`;
  } else { vEl.className = 'demo-verdict info';
    vEl.innerHTML = `➖ <b>No significant trend.</b> ${what} at <b>${loc.short}</b> leans ${dir} (${fmtNum(sr.pd, unit)} per decade, ${start}-${end}), but the year-to-year ups and downs are too large to tell this apart from chance (${tests}).` +
      (sr.yn && sr.yn > n && sr.yn <= 200 ? ` If this trend and noise continued, about <b>${sr.yn} years</b> of data would be needed to call it significant.` : ''); }
  const notes = [];
  if (sr.tr) notes.push('Sunlight and cloud cover are shown for 2001-2025 only, because NASA POWER changes their data source in 2001.');
  if (sr.lag) notes.push('Neighbouring years are correlated, so the p-values may be a little optimistic.');
  if (loc.region && !sr.tr) notes.push('The country average uses yearly values only.');
  nEl.textContent = notes.join(' ');
  const hv = (lbl) => `${lbl} %{x}: %{y:.3f} ${unit}<extra></extra>`;
  Plotly.react('d-chart', [
    {x: years.concat([...years].reverse()), y: fit.map((f, i) => f + half[i]).concat(fit.map((f, i) => f - half[i]).reverse()), fill: 'toself',
     fillcolor: 'rgba(239,68,68,0.14)', line: {width: 0}, name: '95% confidence band ', hoverinfo: 'skip', type: 'scatter'},
    {x: years, y: sr.v, mode: 'lines+markers', name: 'Measured value', line: {color: '#3b82f6', width: 2}, marker: {size: 5}, hovertemplate: hv(''), type: 'scatter'},
    {x: years, y: fit, mode: 'lines', name: 'Linear trend', line: {color: '#ef4444', width: 2.5}, hovertemplate: hv('Trend'), type: 'scatter'},
  ], {paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: {family: 'Inter, sans-serif', color: '#e8edf5', size: 12},
      margin: {l: 52, r: 8, t: 8, b: 30}, hovermode: 'x unified', showlegend: true,
      legend: {orientation: 'h', x: 1, xanchor: 'right', y: 1.12, font: {size: 11}, itemwidth: 30, tracegroupgap: 12},
      xaxis: {gridcolor: 'rgba(148,163,184,0.12)', zeroline: false},
      yaxis: {title: {text: v.unit === 'fraction' ? 'fraction (0-1)' : v.unit, font: {size: 11}}, gridcolor: 'rgba(148,163,184,0.12)', zeroline: false}},
    {displayModeBar: false, responsive: true});
}
dLoc.onchange = () => { fillVars(); renderDemo(); }; dVar.onchange = renderDemo; dSea.onchange = renderDemo;
dLoc.value = 'MNG'; fillVars(); dVar.value = 'T2M'; renderDemo();

// count-up numbers when they scroll into view
function countUp(el) {
  const target = parseFloat(el.dataset.count), dec = +el.dataset.dec, pre = el.dataset.prefix || '', suf = el.dataset.suffix || '';
  const t0 = performance.now(), dur = 1600;
  const step = now => { const p = Math.min(1, (now - t0) / dur), v = target * (1 - Math.pow(1 - p, 3));
    el.textContent = (v >= 0 && pre ? pre : '') + v.toFixed(dec) + suf; if (p < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
const cObs = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { countUp(e.target); cObs.unobserve(e.target); } }), {threshold:.6});
document.querySelectorAll('[data-count]').forEach(el => cObs.observe(el));

// users: click a persona
function showUser(id) {
  const u = USERS.find(x => x.id === id);
  document.querySelectorAll('.ubtn').forEach(b => b.classList.toggle('on', b.dataset.u === id));
  const link = u.link ? `<a class="btn btn-primary btn-sm" style="margin-top:22px" href="${u.link}">Try their mission <span class="arr">→</span></a>` :
    `<p class="muted" style="margin-top:22px; font-size:14px;">Their mission: #${u.mission} (opens in the app once it is online).</p>`;
  document.getElementById('upanel').innerHTML = `<div class="fade"><div class="big">${u.icon}</div>
    <p class="muted" style="margin-top:14px; font-size:14px; text-transform:uppercase; letter-spacing:.12em; font-weight:700;">${u.name} · ${u.who}</p>
    <blockquote>“${u.q}”</blockquote><p class="muted">How they use Trend Detective:</p>
    <ol>${u.how.map(h => `<li>${h}</li>`).join('')}</ol>${u.note ? `<div class="note">${u.note}</div>` : ''}${link}</div>`;
}
document.querySelectorAll('.ubtn').forEach(b => b.onclick = () => showUser(b.dataset.u));
showUser(USERS[0].id);

// how it works: swap the sticky screenshot as each step reaches the middle of the screen
const steps = [...document.querySelectorAll('.steps .step')], shots = [...document.querySelectorAll('#shots img')], sdots = document.getElementById('sdots');
shots.forEach(() => sdots.appendChild(document.createElement('i')));
function setStep(i) { steps.forEach((s, j) => s.classList.toggle('on', j === i)); shots.forEach((s, j) => s.classList.toggle('on', j === i));
  [...sdots.children].forEach((d, j) => d.classList.toggle('on', j === i)); }
const stObs = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) setStep(steps.indexOf(e.target)); }), {rootMargin:'-45% 0px -45% 0px'});
steps.forEach(s => stObs.observe(s)); setStep(0);

// explore: map + scanner
let animTimer = null, animIdx = 0;
function stopAnim() { clearTimeout(animTimer); animTimer = null; }
function animStep() { const fr = FIGS.anim.frames; animIdx = (animIdx + 1) % fr.length;
  Plotly.animate('fig-map', [fr[animIdx].name], {mode:'immediate', frame:{duration:0, redraw:true}, transition:{duration:0}});
  animTimer = setTimeout(animStep, animIdx === fr.length - 1 ? 2000 : 320); }
function showMap(v) {
  stopAnim(); const cap = document.getElementById('map-caption');
  if (v === 'anim') { const f = FIGS.anim; animIdx = 0;
    Plotly.newPlot('fig-map', f.data, f.layout, CONFIG).then(gd => Plotly.addFrames(gd, f.frames)).then(() => animTimer = setTimeout(animStep, 400));
    cap.innerHTML = '<b>Year by year:</b> each frame is one year compared with the 1981-2010 average of the same grid cell.';
  } else { const f = FIGS['map_' + v]; Plotly.newPlot('fig-map', f.data, f.layout, CONFIG); const k = FACTS['map_' + v];
    cap.innerHTML = `<b>${k.label}</b>: Mongolia average ${k.avg} per decade (${k.verdict}). Significant increase over ${k.up}% of the area (${k.up_bh}% after correcting for testing many cells), decrease over ${k.down}% (${k.down_bh}%). Dots show p < 0.05 before that correction.`; }
  document.querySelectorAll('#map-btns .chip').forEach(b => b.classList.toggle('on', b.dataset.v === v));
}
function showScan(site) { const s = SCANS[site];
  document.getElementById('scan-title').innerHTML = `<b>${site}</b>: ${s.n_sig} of ${s.n} variables have a significant trend <span class="muted">· top 8 shown</span>`;
  document.getElementById('scan-body').innerHTML = s.rows;
  document.querySelectorAll('#scan-btns .chip').forEach(b => b.classList.toggle('on', b.dataset.site === site)); }
document.querySelectorAll('#map-btns .chip').forEach(b => b.onclick = () => showMap(b.dataset.v));
document.querySelectorAll('#scan-btns .chip').forEach(b => b.onclick = () => showScan(b.dataset.site));
showMap('T2M'); showScan(Object.keys(SCANS)[1] || Object.keys(SCANS)[0]);
new IntersectionObserver(es => es.forEach(e => { if (!e.isIntersecting) stopAnim(); else if (document.querySelector('#map-btns .chip.on').dataset.v === 'anim' && !animTimer) animStep(); }))
  .observe(document.getElementById('fig-map'));

// findings: seasons / Arctic
function showFind(k) { const f = FIGS[k]; Plotly.newPlot('fig-find', f.data, f.layout, CONFIG);
  document.getElementById('find-caption').innerHTML = FACTS[k + '_caption'];
  document.querySelectorAll('#find-btns .chip').forEach(b => b.classList.toggle('on', b.dataset.fig === k)); }
document.querySelectorAll('#find-btns .chip').forEach(b => b.onclick = () => showFind(b.dataset.fig));
showFind('seasons');

// findings: stripes timeline (hover + one-time scan when it scrolls into view)
const bar = document.getElementById('tlbar'), scanline = document.getElementById('scanline'), readout = document.getElementById('readout');
function stripeAt(clientX) { const r = bar.getBoundingClientRect(); return Math.min(STRIPES.length - 1, Math.max(0, Math.floor((clientX - r.left) / r.width * STRIPES.length))); }
function showTip(e, st) { tip.innerHTML = `<b>${st.y}</b> · ${st.a > 0 ? '+' : ''}${st.a.toFixed(2)} °C vs 1981-2010`; tip.style.left = (e.clientX + 14) + 'px'; tip.style.top = (e.clientY - 40) + 'px'; tip.style.opacity = 1; }
bar.addEventListener('mousemove', e => showTip(e, STRIPES[stripeAt(e.clientX)]));
bar.addEventListener('mouseleave', () => tip.style.opacity = 0);
document.querySelector('.ribbon').addEventListener('mousemove', e => { const r = e.currentTarget.getBoundingClientRect();
  showTip(e, STRIPES[Math.min(STRIPES.length - 1, Math.max(0, Math.floor((e.clientX - r.left) / r.width * STRIPES.length)))]); });
document.querySelector('.ribbon').addEventListener('mouseleave', () => tip.style.opacity = 0);
function runScan() {
  const n = STRIPES.length, w = bar.clientWidth, t0 = performance.now() + 400, dur = 2600;
  const tick = now => { const p = Math.min(1, Math.max(0, (now - t0) / dur)), e = p < .5 ? 2*p*p : 1 - Math.pow(-2*p + 2, 2) / 2;
    if (now >= t0) { const x = e * w, i = Math.min(n - 1, Math.floor(e * n)), st = STRIPES[i];
      scanline.style.left = x + 'px'; readout.style.left = x + 'px'; scanline.style.opacity = readout.style.opacity = p < 1 ? 1 : 0;
      readout.innerHTML = `${st.y} <span style="color:${st.a > 0 ? 'var(--hot)' : 'var(--cool)'}">${st.a > 0 ? '+' : ''}${st.a.toFixed(2)} °C</span>`; }
    if (p < 1) requestAnimationFrame(tick); else document.querySelectorAll('.tl .pin').forEach((pin, k) => setTimeout(() => pin.style.opacity = 1, k * 180)); };
  requestAnimationFrame(tick);
}
const tlObs = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { runScan(); tlObs.unobserve(e.target); } }), {threshold:.6});
tlObs.observe(document.getElementById('tl'));
});
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-url", default="")
    args = ap.parse_args()
    app = args.app_url.rstrip("/")
    def style(f, font_size=13):
        if any(getattr(t, "name", "") == "Mongolia border" for t in f.data):
            f.update_layout(showlegend=False, margin=dict(l=0, r=0, t=40, b=0), height=420)  # the caption explains the dots
        else:
            f.update_layout(height=460)
        return site_style(f, font_size=12 if font_size <= 16 else 13)
    figs, facts, scans, stripes = build_data(style=style)
    t, s, c = facts["t2m"], facts["seasons"], facts["compare"]
    facts["seasons_caption"] = (f"<b>Temperature trend by season:</b> summers warm significantly at {s['summer_sig']} of {s['n']} sites; "
                                f"winters lean colder (average {s['winter_avg']:+.2f} °C per decade), significant at {'none' if s['winter_sig'] == 0 else s['winter_sig']} of the {s['n']}. Faded bars are not significant.")
    facts["compare_caption"] = (f"<b>Opposite trends:</b> Svalbard winters (one Arctic grid point) warmed {c['arctic']:+.2f} °C per decade (Mann-Kendall p = {format_p(c['arctic_p'])}) "
                                f"while Ulaanbaatar winters lean {c['ub']:+.2f} °C ({c['ub_verdict']}). Lines show each place's difference from its own average.")

    n = len(stripes)
    pct = lambda i: (i + 0.5) / n * 100  # noqa: E731
    stripes_html = "".join(f'<i style="background:{st["c"]}"></i>' for st in stripes)
    year_idx = {st["y"]: i for i, st in enumerate(stripes)}
    tl_years = "".join(f'<span style="left:{pct(year_idx[y]):.2f}%">{y}</span>' for y in (1981, 1990, 2000, 2010, 2025) if y in year_idx)
    pins = "".join(
        f'<div class="pin" style="left:{pct(p["i"]):.2f}%"><div class="t">{html.escape(p["label"])}</div>'
        f'<div class="v" style="color:{"var(--hot)" if p["val"].startswith("+") else "var(--cool)"}">{html.escape(p["val"])}</div><div class="stem"></div></div>'
        for p in facts["pins"])
    stats = "".join(
        f'<div class="stat rv" style="--d:{k * 120}"><div class="n{" hot" if k >= 2 else ""}" data-count="{f["n"]}" data-dec="{f["dec"]}" data-suffix="{f["suffix"]}">{f["n"]:.{f["dec"]}f}{f["suffix"]}</div>'
        f'<div class="l">{html.escape(f["label"])}</div><div class="s">Source: <a href="{f["url"]}">{html.escape(f["src"])}</a></div></div>'
        for k, f in enumerate(FACTS))
    users = []
    for u in USERS:
        u = dict(u)
        u["link"] = f"{app}/?mission={u['mission']}" if app else ""
        users.append(u)
    user_buttons = "".join(f'<button class="ubtn" data-u="{u["id"]}"><span class="e">{u["icon"]}</span><span>{html.escape(u["name"])}<small>{html.escape(u["who"])}</small></span></button>' for u in USERS)
    steps = "".join(f'<div class="step"><div class="no">STEP {i + 1}</div><h3>{html.escape(st["t"])}</h3><p>{html.escape(st["d"])}</p></div>' for i, st in enumerate(STEPS))
    shots = "".join(f'<img src="img/{st["img"]}" alt="{html.escape(st["t"])}">' for st in STEPS)
    missions = "".join(
        (f'<a class="mcard rv" style="--d:{(i % 3) * 100}" href="{app}/?mission={i + 1}">' if app else f'<div class="mcard rv" style="--d:{(i % 3) * 100}">')
        + f'<div class="no">MISSION {i + 1}</div><h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p>'
        + (f'<div class="go">Open in the app →</div></a>' if app else '<div class="go muted">Opens in the app once it is online</div></div>')
        for i, (title, desc) in enumerate(MISSIONS))
    if app:
        nav_cta = f'<a class="btn btn-primary btn-sm" href="{html.escape(app)}">Open the app <span class="arr">→</span></a>'
        hero_cta = f'<a class="btn btn-primary" href="{html.escape(app)}">Open the app <span class="arr">→</span></a><a class="btn btn-ghost" href="#explore">Explore the evidence ↓</a>'
        final_cta = f'<a class="btn btn-primary" href="{html.escape(app)}">Open the app <span class="arr">→</span></a>'
    else:
        nav_cta = '<a class="btn btn-primary btn-sm" href="#explore">Explore <span class="arr">↓</span></a>'
        hero_cta = '<a class="btn btn-primary" href="#explore">Explore the evidence <span class="arr">↓</span></a>'
        final_cta = ""

    reps = {
        "__FIGS__": json.dumps(figs, separators=(",", ":")),
        "__FACTS__": json.dumps(facts, separators=(",", ":"), default=float),
        "__SCANS__": json.dumps(scans, separators=(",", ":"), ensure_ascii=False),
        "__STRIPES_JSON__": json.dumps(stripes, separators=(",", ":")),
        "__USERS_JSON__": json.dumps(users, ensure_ascii=False),
        "__DEMO_JSON__": json.dumps(build_demo(), separators=(",", ":"), ensure_ascii=False),
        "__DEMO_CTA__": (f'<a href="{html.escape(app)}">Open the full app ↗</a><br>' if app else "")
                        + "The full app adds the clickable map, year-by-year animation, scanner, compare mode and guided missions.",
        "__RIBBON__": stripes_html, "__TL_STRIPES__": stripes_html, "__TL_YEARS__": tl_years, "__PINS__": pins,
        "__STATS__": stats, "__USER_BUTTONS__": user_buttons, "__STEPS__": steps, "__SHOTS__": shots, "__MISSIONS__": missions,
        "__MAP_BUTTONS__": "".join(f'<button class="chip" data-v="{v}">{html.escape(C.VARIABLES[v]["label"])}</button>' for v in MAP_VARS),
        "__SCAN_BUTTONS__": "".join(f'<button class="chip" data-site="{html.escape(k)}">{html.escape(k)}</button>' for k in scans),
        "__T2M_RATE__": f"{t['rate']:.4f}", "__T2M_P__": format_p(t["p"]), "__WARM__": f"{t['warm']:.0f}", "__COOL__": f"{t['cool']:.0f}", "__WARM_BH__": f"{t['warm_bh']:.0f}", "__CELLS__": str(t["cells"]),
        "__T2M_RATE_TXT__": f"{t['rate']:+.2f} °C", "__WIND_RATE_TXT__": f"{facts['wind']['rate']:.2f} m/s",
        "__WIND_RATE__": f"{facts['wind']['rate']:.4f}", "__WIND_VERDICT__": facts["wind"]["verdict"],
        "__SUMMER_SIG__": str(s["summer_sig"]), "__NSITES__": str(s["n"]), "__WINTER_AVG__": f"{s['winter_avg']:+.2f}", "__ARCTIC__": f"{c['arctic']:+.2f}",
        "__NAV_CTA__": nav_cta, "__HERO_CTA__": hero_cta, "__FINAL_CTA__": final_cta,
        "__SLIDES__": SLIDES_URL, "__PDF_URL__": PDF_URL, "__REPO__": REPO,
    }
    page = PAGE
    for k, v in reps.items():
        page = page.replace(k, v)
    left = set(re.findall(r"__[A-Z0-9_]+__", page))
    assert not left, f"unfilled placeholders: {left}"

    (DOCS / "img").mkdir(parents=True, exist_ok=True)
    (DOCS / "index.html").write_text(page)
    (DOCS / ".nojekyll").write_text("")
    for name in {"app.png", "og.png", *(st["img"] for st in STEPS)}:
        shutil.copy(ROOT / "demo" / "img" / name, DOCS / "img" / name)
    shutil.copy(Path(plotly.__file__).parent / "package_data" / "plotly.min.js", DOCS / "plotly.min.js")
    print(f"wrote docs/index.html ({(DOCS / 'index.html').stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
