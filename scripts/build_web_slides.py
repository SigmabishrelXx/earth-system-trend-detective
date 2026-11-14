"""Build the cinematic, interactive 7-slide web presentation (docs/index.html) for GitHub Pages.

    python3 scripts/build_web_slides.py                          # GitHub link only
    python3 scripts/build_web_slides.py --app-url https://...    # also link the live app

Design: see demo/STORYBOARD.md. Two persistent elements morph between slides (the title shrinks into a corner
logo; Mongolia's temperature stripes go from full-bleed backdrop to a timeline band and back). Every chart is a
live Plotly figure from trend_detective.figures using the bundled NASA POWER data. Plotly.js is copied next to
the page, so nothing has to be installed and no CDN is needed for the charts.

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

import numpy as np
import pandas as pd
import plotly
import plotly.colors as pcolors
import plotly.io as pio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trend_detective import catalog as C  # noqa: E402
from trend_detective.analysis import analyze, benjamini_hochberg, format_num, format_p, grid_trends  # noqa: E402
from trend_detective.data import country_average, load_boundary, load_grid, load_point, seasonal_series, source_consistent  # noqa: E402
from trend_detective.figures import anomaly_animation, compare_figure, map_figure, seasons_figure, slide_style  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO = "https://github.com/SigmabishrelXx/earth-system-trend-detective"
PDF_URL = f"{REPO}/blob/main/demo/Earth_System_Trend_Detective_slides.pdf"
MAP_VARS = ["T2M", "WS2M", "PRECTOTCORR", "GWETROOT", "FROST_DAYS", "SNODP"]
Y0, Y1 = C.START_YEAR, C.END_YEAR
BAND = dict(x=104, y=330, w=1712, h=210)  # timeline band on slide 5 (canvas px)


def _round(obj, nd: int = 4):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, list):
        return [_round(v, nd) for v in obj]
    if isinstance(obj, dict):
        return {k: _round(v, nd) for k, v in obj.items()}
    return obj


def fig_json(fig) -> dict:
    return _round(json.loads(pio.to_json(fig, validate=False)))


def area_share(tr: pd.DataFrame, mask) -> float:
    w = np.cos(np.radians(tr["Lat"]))
    return float(w[mask].sum() / w.sum() * 100)


def verdict_icon(r) -> str:
    return {"significant": "✅", "mixed": "⚠️", "not significant": "➖"}[r.verdict]


def build_data(style=slide_style):
    grid = load_grid()
    boundary = load_boundary()
    figs, facts = {}, {}

    # Temperature stripes: Mongolia-average T2M difference from 1981-2010, one stripe per year
    nat = country_average(grid, "T2M")
    base = nat[(nat["Year"] >= 1981) & (nat["Year"] <= 2010)]["Value"].mean()
    anom = (nat["Value"] - base).to_numpy()
    lim = float(np.max(np.abs(anom)))
    colors = pcolors.sample_colorscale("RdBu_r", list((anom + lim) / (2 * lim)))
    stripes = [{"y": int(y), "a": round(float(a), 2), "c": c} for y, a, c in zip(nat["Year"], anom, colors)]
    hot, cold = int(np.argmax(anom)), int(np.argmin(anom))
    facts["pins"] = [
        {"i": cold, "label": f"{stripes[cold]['y']} · coldest", "val": f"{anom[cold]:+.2f} °C"},
        {"i": hot, "label": f"{stripes[hot]['y']} · hottest", "val": f"{anom[hot]:+.2f} °C"},
        {"i": len(stripes) - 1, "label": f"{stripes[-1]['y']} · latest", "val": f"{anom[-1]:+.2f} °C"},
    ]

    # Slide 4: trend maps (switchable) and the year-by-year animation
    for var in MAP_VARS:
        sub = grid[(grid["Variable"] == var) & grid["InMongolia"]]
        tr = grid_trends(sub, Y0, Y1)
        r = analyze(country_average(grid, var))
        sig = tr["PMK"] < 0.05
        facts[f"map_{var}"] = {
            "label": C.VARIABLES[var]["label"], "avg": format_num(r.per_decade, C.VARIABLES[var]["unit"]),
            "verdict": r.verdict, "up": round(area_share(tr, sig & (tr["PerDecade"] > 0))),
            "down": round(area_share(tr, sig & (tr["PerDecade"] < 0))),
            "up_bh": round(area_share(tr, benjamini_hochberg(tr["PMK"].to_numpy()) & (tr["PerDecade"] > 0))),
            "down_bh": round(area_share(tr, benjamini_hochberg(tr["PMK"].to_numpy()) & (tr["PerDecade"] < 0))),
        }
        f = map_figure(tr, var, boundary, height=540)
        for trace in f.data:
            if trace.name == "cells":
                trace.hovertemplate = trace.hovertemplate.replace("<extra>Click to explore</extra>", "<extra></extra>")
        f.update_layout(margin=dict(l=0, r=0, t=36, b=0))
        figs[f"map_{var}"] = style(f, font_size=16)
        if var == "T2M":
            facts["t2m"] = {"rate": r.per_decade, "p": r.mk.p, "total": r.total_change,
                            "warm": area_share(tr, sig & (tr["PerDecade"] > 0)),
                            "cool": area_share(tr, sig & (tr["PerDecade"] < 0)),
                            "warm_bh": area_share(tr, benjamini_hochberg(tr["PMK"].to_numpy()) & (tr["PerDecade"] > 0)),
                            "cells": len(tr)}
        if var == "WS2M":
            facts["wind"] = {"rate": r.per_decade, "verdict": r.verdict}
    gv = grid[(grid["Variable"] == "T2M") & grid["InMongolia"]]
    anim = anomaly_animation(gv, "T2M", boundary, height=540)
    anim.layout.sliders = ()
    anim.layout.updatemenus = ()
    anim.update_layout(showlegend=False, margin=dict(l=0, r=0, t=56, b=0))
    figs["anim"] = style(anim, font_size=18)

    # Slide 4: scanner tables for the Mongolian sites; slide 6: seasons chart
    scans, seasons_rows = {}, []
    order = {"significant": 0, "mixed": 1, "not significant": 2}
    for site in C.MONGOLIA_SITES:
        lat, lon, _ = C.LOCATIONS[site]
        monthly, _ = load_point(lat, lon)
        rows = []
        for var in C.VARIABLES:
            s, trimmed = source_consistent(var, seasonal_series(monthly, var, "Whole year"))
            if len(s) >= 5 and s["Value"].std() > 0:
                rows.append((var, analyze(s), trimmed))
        rows.sort(key=lambda t: (order[t[1].verdict], t[1].mk.p))
        body = "".join(
            f'<tr class="{r.verdict.replace(" ", "-")}"><td>{verdict_icon(r)}</td><td>{html.escape(C.VARIABLES[v]["label"])}'
            f'{"<sup>*</sup>" if trimmed else ""}</td>'
            f'<td class="r">{html.escape(format_num(r.per_decade, C.VARIABLES[v]["unit"]))}</td>'
            f'<td class="r">{"↑" if r.slope > 0 else "↓"}</td><td class="r">{html.escape(format_p(r.mk.p))}</td>'
            f'<td class="r">{html.escape(format_p(r.p_linear))}</td></tr>'
            for v, r, trimmed in rows[:8])
        scans[site.split(" (")[0]] = {"n_sig": sum(r.verdict == "significant" for _, r, _ in rows), "n": len(rows), "rows": body}
        for season in list(C.SEASONS)[1:]:
            r = analyze(seasonal_series(monthly, "T2M", season))
            seasons_rows.append((site.split(" (")[0], season.split(" ")[0].lower(), r.per_decade, r.verdict == "significant"))
    sdf = pd.DataFrame(seasons_rows, columns=["Site", "Season", "PerDecade", "Significant"])
    figs["seasons"] = style(seasons_figure(sdf, height=540), font_size=18)
    summer, winter = sdf[sdf["Season"] == "summer"], sdf[sdf["Season"] == "winter"]
    facts["seasons"] = {"summer_sig": int(summer["Significant"].sum()), "n": len(summer),
                        "winter_sig": int(winter["Significant"].sum()), "winter_avg": float(winter["PerDecade"].mean())}

    # Slide 6: warm Arctic vs Ulaanbaatar winters
    def winter_series(name):
        lat, lon, _ = C.LOCATIONS[name]
        s = seasonal_series(load_point(lat, lon)[0], "T2M", "Winter (Dec-Feb)")
        return s, analyze(s)
    a, ra = winter_series("Ulaanbaatar (capital)")
    b, rb = winter_series("Arctic (Svalbard, Norway)")
    cf = compare_figure(a, ra, "Ulaanbaatar", b, rb, "Svalbard (Arctic)", "T2M", height=540)
    cf.update_layout(title=None, margin=dict(l=10, r=10, t=40, b=10))
    figs["compare"] = style(cf, font_size=18)
    facts["compare"] = {"ub": ra.per_decade, "ub_verdict": ra.verdict, "arctic": rb.per_decade, "arctic_p": rb.mk.p}
    return {k: fig_json(v) for k, v in figs.items()}, facts, scans, stripes


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Earth System Trend Detective · Team Florensiza · NASA Space Apps 2026</title>
<meta name="description" content="Interactive 7-slide demo for the NASA Space Apps Challenge 2026 challenge Be An Earth System Trend Detective! by Team Florensiza (Bishrel), Ulaanbaatar. Made with help from Claude Code (AI).">
<meta name="author" content="Bishrel (Team Florensiza)">
<meta property="og:title" content="Earth System Trend Detective · 7-slide demo">
<meta property="og:description" content="Is Mongolia's climate really changing? NASA data, honest statistics. NASA Space Apps 2026, Team Florensiza.">
<meta property="og:image" content="https://sigmabishrelxx.github.io/earth-system-trend-detective/img/og.png">
<meta property="og:url" content="https://sigmabishrelxx.github.io/earth-system-trend-detective/slides/">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Ctext y=%22.9em%22 font-size=%2290%22%3E%F0%9F%94%8E%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="../plotly.min.js" defer></script>
<style>
  :root { --bg:#0b0f17; --panel:rgba(18,24,38,.82); --line:#243045; --text:#e8edf5; --muted:#93a1b8; --hot:#ff6b4a; --cool:#4d9fff;
          --teal:#2dd4bf; --gold:#fbbf24; --ease:cubic-bezier(.65,0,.35,1); --out:cubic-bezier(.16,1,.3,1);
          --display:"Archivo", "Helvetica Neue", Arial, sans-serif; --body:"Inter", -apple-system, "Helvetica Neue", Arial, sans-serif; }
  * { box-sizing:border-box; margin:0; padding:0; }
  html, body { height:100%; background:#05070b; color:var(--text); overflow:hidden; font-family:var(--body); }
  #viewport { position:fixed; inset:0; display:flex; align-items:center; justify-content:center; }
  #stage { width:1920px; height:1080px; position:relative; transform-origin:center center; flex:none; overflow:hidden;
           background: radial-gradient(1200px 800px at 85% 0%, rgba(255,107,74,.08), transparent 60%), var(--bg); }

  /* ---------- persistent layer 1: temperature stripes ---------- */
  #stripes { position:absolute; left:0; top:0; width:1920px; height:1080px; display:flex; transform-origin:0 0; z-index:1;
             transition: transform 1.15s var(--ease), opacity 1.15s var(--ease); pointer-events:none; }
  #stripes i { flex:1; display:block; }
  #stripes.wipe { animation: wipe 1.8s var(--out) both; }
  @keyframes wipe { from { clip-path: inset(0 100% 0 0); } to { clip-path: inset(0 0 0 0); } }
  #shade { position:absolute; inset:0; z-index:2; pointer-events:none; transition: opacity 1s var(--ease);
           background: linear-gradient(90deg, rgba(11,15,23,.94) 0%, rgba(11,15,23,.80) 42%, rgba(11,15,23,.35) 100%),
                       linear-gradient(0deg, rgba(11,15,23,.85) 0%, rgba(11,15,23,0) 35%); }
  #stage[data-s="1"] #stripes { transform:none; opacity:1; }
  #stage[data-s="2"] #stripes { transform:translate(-120px,-54px) scale(1.1); opacity:.10; }
  #stage[data-s="3"] #stripes { transform:translate(-170px,-54px) scale(1.1); opacity:.08; }
  #stage[data-s="4"] #stripes { transform:translate(-220px,-54px) scale(1.1); opacity:.06; }
  #stage[data-s="5"] #stripes { transform:translate(__BX__px,__BY__px) scale(__SX__,__SY__); opacity:1; pointer-events:auto; cursor:crosshair; }
  #stage[data-s="6"] #stripes { transform:translate(-260px,-54px) scale(1.1); opacity:.07; }
  #stage[data-s="7"] #stripes { transform:none; opacity:.75; }
  #stage[data-s="1"] #shade, #stage[data-s="7"] #shade { opacity:1; }
  #stage:not([data-s="1"]):not([data-s="7"]) #shade { opacity:0; }

  /* ---------- persistent layer 2: the title that morphs into a corner logo ---------- */
  #brand { position:absolute; left:104px; top:300px; z-index:5; transform-origin:0 0; font-family:var(--display);
           font-stretch:125%; font-weight:900; font-size:96px; line-height:.98; letter-spacing:.005em; text-transform:uppercase;
           transition: transform 1.15s var(--ease); white-space:nowrap; pointer-events:none; }
  #brand .hot { color:var(--hot); }
  #stage:not([data-s="1"]) #brand { transform: translate(0,-262px) scale(.205); }
  #brand.intro { animation: titleIn 1.6s var(--out) .9s both; }
  @keyframes titleIn { from { opacity:0; letter-spacing:.35em; filter:blur(8px); } to { opacity:1; letter-spacing:.005em; filter:blur(0); } }

  /* ---------- slides ---------- */
  .slide { position:absolute; inset:0; padding:118px 104px 100px; z-index:3; pointer-events:none; visibility:hidden; }
  .slide.active, .slide.leaving { visibility:visible; }
  .slide.active > * { pointer-events:auto; }
  .slide.active > .abs { pointer-events:none; }
  [data-a] { opacity:0; }
  .slide.active [data-a] { animation: var(--anim, up) .95s var(--out) both; animation-delay: calc(var(--d, 0) * 1ms); }
  .slide.leaving [data-a] { animation: leave .38s var(--ease) both; }
  #stage.from-title .slide.active [data-a] { animation-delay: calc((var(--d, 0) + 520) * 1ms); }
  [data-a="up"] { --anim:up; } [data-a="fade"] { --anim:fade; } [data-a="side"] { --anim:side; } [data-a="lens"] { --anim:lens; }
  [data-a="reveal3d"] { --anim:reveal3d; }
  @keyframes up { from { opacity:0; transform:translateY(46px); } to { opacity:1; transform:none; } }
  @keyframes fade { from { opacity:0; } to { opacity:1; } }
  @keyframes side { from { opacity:0; transform:translateX(calc(var(--dir,1) * 90px)); } to { opacity:1; transform:none; } }
  @keyframes lens { from { opacity:0; transform:scale(1.08); filter:blur(10px); } to { opacity:1; transform:none; filter:blur(0); } }
  @keyframes reveal3d { from { opacity:0; transform:perspective(1800px) translateX(160px) rotateY(-22deg); }
                        to { opacity:1; transform:perspective(1800px) translateX(0) rotateY(0deg); } }
  @keyframes leave { from { opacity:1; transform:none; } to { opacity:0; transform:translateX(calc(var(--dir,1) * -70px)); } }

  .kicker { font-size:21px; letter-spacing:.3em; text-transform:uppercase; color:var(--hot); font-weight:700; }
  h2 { font-family:var(--display); font-stretch:115%; font-size:64px; line-height:1.04; font-weight:850; letter-spacing:-.005em; margin-top:16px; }
  h3 { font-family:var(--display); font-stretch:110%; font-size:34px; font-weight:800; margin-bottom:12px; }
  p, li { font-size:30px; line-height:1.4; }
  .muted { color:var(--muted); } .hot { color:var(--hot); } .cool { color:var(--cool); } .teal { color:var(--teal); } .gold { color:var(--gold); }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:22px; padding:30px 34px; }
  ul.clean { list-style:none; } ul.clean li { padding-left:44px; position:relative; margin-bottom:22px; font-size:31px; }
  ul.clean li::before { content:""; position:absolute; left:0; top:15px; width:20px; height:20px; border-radius:5px; background:var(--hot); }
  ul.clean.teal li::before { background:var(--teal); }
  .num { display:inline-flex; width:52px; height:52px; border-radius:50%; align-items:center; justify-content:center; background:var(--hot);
         color:#0b0f17; font-weight:800; font-size:26px; flex:none; font-family:var(--display); }
  .step { display:flex; gap:20px; align-items:flex-start; margin-bottom:24px; }
  .step b { display:block; font-family:var(--display); font-stretch:110%; font-size:30px; margin-bottom:4px; }
  .step span { font-size:24px; line-height:1.35; color:var(--muted); }
  .btns { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }
  .btn { font:inherit; font-size:21px; padding:9px 18px; border-radius:999px; border:1px solid var(--line); background:var(--panel);
         color:var(--muted); cursor:pointer; transition:all .15s; }
  .btn:hover { color:var(--text); border-color:#3a4a66; } .btn.on { background:var(--hot); color:#0b0f17; border-color:var(--hot); font-weight:700; }
  .caption { font-size:22px; color:var(--muted); margin-top:10px; line-height:1.4; }
  .shot { width:100%; border-radius:18px; border:1px solid var(--line); box-shadow:0 40px 100px rgba(0,0,0,.6); display:block; }
  table.scan { width:100%; border-collapse:collapse; font-size:22px; }
  table.scan td { padding:8px 10px; border-bottom:1px solid var(--line); } table.scan td.r { text-align:right; white-space:nowrap; }
  table.scan tr.significant td { color:var(--text); } table.scan tr.mixed td, table.scan tr.not-significant td { color:var(--muted); }
  table.scan th { text-align:left; font-size:18px; color:var(--muted); font-weight:600; padding:6px 10px; border-bottom:1px solid var(--line); }
  a { color:var(--teal); text-decoration:none; } a:hover { text-decoration:underline; }
  .cta { display:inline-block; margin-top:14px; padding:14px 26px; border-radius:14px; background:var(--hot); color:#0b0f17 !important;
         font-weight:800; font-size:26px; text-decoration:none !important; }
  .abs { position:absolute; }
  .chip { display:inline-block; padding:8px 16px; border-radius:999px; border:1px solid var(--line); background:var(--panel);
          font-size:20px; color:var(--muted); margin:0 8px 8px 0; }
  .chip b { color:var(--text); }

  /* slide 5 timeline overlay */
  #scan { position:absolute; top:__BY__px; height:__BH__px; width:3px; background:#fff; box-shadow:0 0 18px 4px rgba(255,255,255,.7);
          left:__BX__px; opacity:0; z-index:4; pointer-events:none; }
  #readout { position:absolute; top:calc(__BY__px - 60px); font-family:var(--display); font-stretch:115%; font-weight:800; font-size:34px;
             transform:translateX(-50%); white-space:nowrap; opacity:0; z-index:4; pointer-events:none; }
  .pin { position:absolute; transform:translateX(-50%); text-align:center; z-index:4; pointer-events:none; }
  .pin .stem { width:2px; height:22px; background:#fff; margin:4px auto 0; opacity:.8; }
  .pin .t { font-size:19px; color:var(--muted); white-space:nowrap; } .pin .v { font-family:var(--display); font-weight:800; font-size:25px; }
  .yr { position:absolute; top:calc(__BY__px + __BH__px + 12px); font-size:19px; color:var(--muted); transform:translateX(-50%); }
  #tip { position:absolute; z-index:6; pointer-events:none; padding:6px 12px; border-radius:10px; background:#0b0f17; border:1px solid var(--line);
         font-size:20px; opacity:0; transition:opacity .15s; white-space:nowrap; }
  .stat .big { font-family:var(--display); font-stretch:115%; font-size:84px; font-weight:900; line-height:1; letter-spacing:-.01em; }
  .stat .lbl { font-size:24px; color:var(--muted); margin-top:10px; line-height:1.3; }

  /* nav */
  #nav { position:fixed; right:14px; bottom:12px; display:flex; align-items:center; gap:12px; padding:6px 10px; z-index:10;
         background:rgba(11,15,23,.72); border:1px solid var(--line); border-radius:999px; }
  .navbtn { width:36px !important; height:36px !important; font-size:19px !important; }
  .navbtn { width:44px; height:44px; border-radius:50%; border:1px solid var(--line); background:rgba(18,24,38,.85); color:var(--text); font-size:22px; cursor:pointer; }
  .navbtn:disabled { opacity:.3; cursor:default; }
  #dots { display:flex; gap:8px; } .dot { width:10px; height:10px; border-radius:50%; background:#334155; cursor:pointer; border:none; transition:all .3s; }
  .dot.on { background:var(--hot); width:26px; border-radius:6px; }
  #count { font-size:14px; color:var(--muted); min-width:48px; text-align:center; }
  #progress { position:fixed; top:0; left:0; height:3px; background:var(--hot); transition:width .5s var(--ease); z-index:11; }
  #help { position:fixed; top:10px; right:14px; font-size:13px; color:var(--muted); z-index:11; }
  @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration:.01ms !important; animation-delay:0ms !important; transition-duration:.01ms !important; } }
</style>
</head>
<body>
<div id="progress"></div>
<div id="help">← → keys, click or swipe · <a href="__PDF_URL__">PDF version</a></div>
<div id="viewport"><div id="stage" data-s="1">

<div id="stripes" class="wipe">__STRIPES__</div>
<div id="shade"></div>
<div id="brand" class="intro">Earth System<br>Trend <span class="hot">Detective</span></div>
<div id="tip"></div>

<!-- 1 · Cold open -->
<section class="slide" data-title="Title">
  <div class="kicker abs" style="left:104px; top:200px; --d:300" data-a="fade">NASA Space Apps Challenge 2026</div>
  <p class="abs muted" style="left:104px; top:238px; font-size:28px; --d:400" data-a="fade">Challenge: <b style="color:var(--text)">Be An Earth System Trend Detective!</b></p>
  <p class="abs" style="left:104px; top:540px; font-size:40px; line-height:1.3; --d:1700" data-a="up">45 years of NASA data. One question:<br>is Mongolia's climate <span class="hot">really</span> changing?</p>
  <div class="abs" style="left:104px; top:745px; font-size:29px; line-height:1.65; --d:2000" data-a="up">
    <div><span class="muted">Team</span> <b>Florensiza</b> &nbsp;·&nbsp; <span class="muted">Member</span> <b>Bishrel</b></div>
    <div><span class="muted">Local event</span> <b>Ulaanbaatar, Mongolia</b></div>
  </div>
  <p class="abs muted" style="right:104px; bottom:96px; width:620px; text-align:right; font-size:20px; line-height:1.4; --d:2300" data-a="fade">
    Each stripe is one year, 1981-2025: Mongolia's average temperature compared with 1981-2010
    (blue cooler, red warmer). NASA POWER / MERRA-2.</p>
</section>

<!-- 2 · The case -->
<section class="slide" data-title="The case">
  <div class="kicker" data-a="fade">The case</div>
  <h2 data-a="side" style="--d:120; max-width:1500px;">Is Mongolia's climate really changing?<br><span class="muted" style="font-weight:700;">Finding out is harder than it sounds.</span></h2>
  <div style="display:grid; grid-template-columns:1fr 1fr; gap:40px; margin-top:56px;">
    <div class="card" data-a="up" style="--d:350">
      <h3 class="hot" style="font-size:38px;">Why it's hard</h3>
      <ul class="clean" style="margin-top:22px;">
        <li>Hundreds of Earth variables. <b>Which ones</b> are changing?</li>
        <li>One process can push a variable <b>up in one region and down in another</b>.</li>
        <li>A few warm years can look like a trend. Is it <b>significant</b>, or chance?</li>
      </ul>
    </div>
    <div class="card" data-a="up" style="--d:520">
      <h3 class="teal" style="font-size:38px;">Why it matters in Mongolia</h3>
      <ul class="clean teal" style="margin-top:22px;">
        <li><b>Dzud</b>: harsh winters after dry summers can kill millions of livestock.</li>
        <li><b>Desertification</b> and dust storms in the Gobi.</li>
        <li><b>Permafrost thaw</b> in the north.</li>
      </ul>
    </div>
  </div>
  <p data-a="fade" style="--d:800; margin-top:34px; font-size:27px;"><span class="muted">Built for:</span> high-school and university students, and curious citizens. No coding needed.</p>
</section>

<!-- 3 · The tool -->
<section class="slide" data-title="The tool">
  <div class="kicker" data-a="fade">The tool</div>
  <h2 data-a="side" style="--d:120;">Pick a variable. Pick a place.<br>Get a verdict.</h2>
  <div style="display:grid; grid-template-columns:600px 940px; gap:68px; margin-top:44px; align-items:start;">
    <div>
      <div class="step" data-a="up" style="--d:500"><div class="num">1</div><div><b>What?</b><span>14 NASA variables, each with a simple definition.</span></div></div>
      <div class="step" data-a="up" style="--d:650"><div class="num">2</div><div><b>Where?</b><span>Any point on Earth, 5 Mongolian regions, or all of Mongolia. Click the map to explore any cell.</span></div></div>
      <div class="step" data-a="up" style="--d:800"><div class="num">3</div><div><b>When?</b><span>Whole year or one season, 1981-2025. Watch the map change year by year.</span></div></div>
      <div class="step" data-a="up" style="--d:950"><div class="num">4</div><div><b>Is it real?</b><span>t-test + 95% confidence interval, Mann-Kendall test, Sen's slope. "Significant" only when both agree.</span></div></div>
    </div>
    <div data-a="reveal3d" style="--d:250">
      <img src="../img/app.png" class="shot" alt="The Earth System Trend Detective app">
      <div class="caption">The real app: missions ask students to guess first, then show the evidence. __APP_LINK__</div>
    </div>
  </div>
</section>

<!-- 4 · Detective tools -->
<section class="slide" data-title="Detective tools">
  <div class="kicker" data-a="fade">Detective tools · try them</div>
  <h2 data-a="side" style="--d:120;">See <span class="hot">where</span> it changes, and <span class="teal">what</span> changes</h2>
  <div style="display:grid; grid-template-columns:1.2fr 1fr; gap:44px; margin-top:26px; align-items:start;">
    <div data-a="lens" style="--d:300">
      <div class="btns" id="map-btns">__MAP_BUTTONS__<button class="btn" data-v="anim">▶ Year by year</button></div>
      <div id="fig-map" style="height:540px;"></div>
      <div class="caption" id="map-caption"></div>
    </div>
    <div data-a="side" style="--d:500">
      <div class="btns" id="scan-btns">__SCAN_BUTTONS__</div>
      <div class="card" style="padding:18px 22px;">
        <p style="font-size:23px; margin-bottom:8px;" id="scan-title"></p>
        <table class="scan"><thead><tr><th></th><th>Variable</th><th style="text-align:right">per decade</th><th></th><th style="text-align:right">MK p</th><th style="text-align:right">t p</th></tr></thead>
        <tbody id="scan-body"></tbody></table>
      </div>
      <div class="caption">Sorted by verdict, then Mann-Kendall p. ✅ both tests significant · ⚠️ only one (often a jump or outlier) · ➖ neither. * Sunlight and cloud tested on 2001-2025 only (data source changes in 2001).</div>
    </div>
  </div>
</section>

<!-- 5 · The evidence: timeline -->
<section class="slide" data-title="The evidence">
  <div class="kicker" data-a="fade">The evidence · NASA POWER, 1981-2025</div>
  <h2 data-a="side" style="--d:120;">Mongolia is warming</h2>
  <div id="scan"></div><div id="readout"></div>
  __PINS__
  __YEARS__
  <div class="abs" style="left:104px; right:104px; top:640px; display:grid; grid-template-columns:repeat(3, 1fr); gap:40px;">
    <div class="stat" data-a="up" style="--d:2200"><div class="big hot" data-count="__T2M_RATE__" data-dec="2" data-prefix="+" data-suffix=" °C">__T2M_RATE_TXT__</div>
      <div class="lbl">per decade, Mongolia average.<br>Significant (Mann-Kendall p = __T2M_P__).</div></div>
    <div class="stat" data-a="up" style="--d:2350"><div class="big hot" data-count="__WARM__" data-dec="0" data-suffix="%">__WARM__%</div>
      <div class="lbl">of Mongolia's area warming significantly<br>(__WARM_BH__% after correcting for __CELLS__ tests).</div></div>
    <div class="stat" data-a="up" style="--d:2500"><div class="big teal" data-count="__WIND_RATE__" data-dec="2" data-suffix=" m/s">__WIND_RATE_TXT__</div>
      <div class="lbl">per decade: wind is slowing on average across<br>Mongolia (__WIND_VERDICT__), but not everywhere.</div></div>
  </div>
  <div class="abs" style="left:104px; bottom:96px; --d:2700" data-a="fade">
    <span class="chip"><b>NASA POWER</b> · Langley Research Center</span><span class="chip"><b>MERRA-2</b> · NASA GMAO model</span>
    <span class="chip"><b>CERES</b> · NASA satellites</span><span class="chip">Tests: <b>t-test + 95% CI · Mann-Kendall · Sen's slope</b></span>
  </div>
</section>

<!-- 6 · The twist -->
<section class="slide" data-title="The twist">
  <div class="kicker" data-a="fade">The twist</div>
  <h2 data-a="side" style="--d:120;">…but not evenly</h2>
  <div style="display:grid; grid-template-columns:560px 1fr; gap:56px; margin-top:34px; align-items:start;">
    <div>
      <p data-a="up" style="--d:350; font-size:31px;"><b class="hot">Summers</b> warm significantly at __SUMMER_SIG__ of __NSITES__ Mongolian sites.</p>
      <p data-a="up" style="--d:500; font-size:31px; margin-top:22px;"><b class="cool">Winters</b> lean colder (__WINTER_AVG__ °C per decade), but not significantly.</p>
      <p data-a="up" style="--d:650; font-size:31px; margin-top:22px;">Meanwhile <b class="hot">Svalbard winters</b> (one Arctic grid point) warm __ARCTIC__ °C per decade.</p>
      <p data-a="up" style="--d:800; font-size:24px; margin-top:28px;" class="muted">One variable, opposite directions. Whether the two are connected ("warm Arctic, cold continent") is a debated idea to test, not proof.</p>
    </div>
    <div data-a="lens" style="--d:300">
      <div class="btns" id="find-btns"><button class="btn on" data-fig="seasons">Seasons at 5 sites</button><button class="btn" data-fig="compare">Svalbard vs Ulaanbaatar winters</button></div>
      <div id="fig-find" style="height:540px;"></div>
      <div class="caption" id="find-caption"></div>
    </div>
  </div>
</section>

<!-- 7 · Closing -->
<section class="slide" data-title="Next">
  <div class="kicker" data-a="fade">What's next</div>
  <h2 data-a="side" style="--d:120;">Every student can be a<br>climate trend detective</h2>
  <div style="display:grid; grid-template-columns:1.05fr 1fr; gap:56px; margin-top:44px; align-items:start;">
    <ul class="clean" data-a="up" style="--d:400">
      <li><b>Mongolian-language version</b> for schools and herder communities.</li>
      <li><b>More NASA data:</b> GLDAS soil water and streamflow, MODIS vegetation greenness.</li>
      <li><b>Seasonal trend maps</b> and more classroom missions.</li>
      <li><b>Smarter tests</b> that correct for year-to-year memory.</li>
    </ul>
    <div class="card" data-a="side" style="--d:600; padding:38px 42px;">
      <h3 style="font-size:40px;">Try it</h3>
      __APP_CTA__
      <p style="font-size:25px; margin-top:16px;"><span class="muted">Code:</span><br><a href="__REPO__">github.com/SigmabishrelXx/earth-system-trend-detective</a></p>
      <p style="font-size:22px; margin-top:16px;" class="muted">Teachers can share a ready-made mission: add <b style="color:var(--text)">?mission=3</b> to the app link. Open source, MIT License.</p>
    </div>
  </div>
  <p class="abs muted" data-a="fade" style="--d:900; left:104px; right:104px; bottom:84px; font-size:19px; line-height:1.45;">
    Data: NASA Langley Research Center (LaRC) POWER Project. Stripes style inspired by Ed Hawkins' warming stripes. Starting code: kdmayer/nasa-power-api (MIT). NASA does not endorse this project.<br>
    AI use: the app's code and these slides were made with help from Claude Code (an AI assistant); every number comes from NASA data, computed by the app.</p>
</section>

</div></div>
<div id="nav">
  <button class="navbtn" id="prev" aria-label="Previous slide">‹</button>
  <div id="dots"></div><div id="count"></div>
  <button class="navbtn" id="next" aria-label="Next slide">›</button>
</div>

<script>
document.addEventListener("DOMContentLoaded", () => {
const FIGS = __FIGS__, FACTS = __FACTS__, SCANS = __SCANS__, STRIPES = __STRIPES_JSON__;
const BAND = __BAND__;
const CONFIG = {displaylogo:false, responsive:true, modeBarButtonsToRemove:['lasso2d','select2d','toImage']};
const stage = document.getElementById('stage');
function fit() { const s = Math.min(innerWidth/1920, innerHeight/1080); stage.style.transform = `scale(${s})`; }
addEventListener('resize', fit); fit();
let cur = -1;

// ---------- slide 4: maps (incl. year-by-year animation) + scanner ----------
let animTimer = null, animIdx = 0, mapView = 'T2M';
function stopAnim() { clearTimeout(animTimer); animTimer = null; }
function animStep() {
  const fr = FIGS.anim.frames; animIdx = (animIdx + 1) % fr.length;
  Plotly.animate('fig-map', [fr[animIdx].name], {mode:'immediate', frame:{duration:0, redraw:true}, transition:{duration:0}});
  animTimer = setTimeout(animStep, animIdx === fr.length - 1 ? 2000 : 320);
}
function showMap(v) {
  mapView = v; stopAnim();
  const cap = document.getElementById('map-caption');
  if (v === 'anim') {
    const f = FIGS.anim; animIdx = 0;
    Plotly.newPlot('fig-map', f.data, f.layout, CONFIG).then(gd => Plotly.addFrames(gd, f.frames)).then(() => { if (cur === 3) animTimer = setTimeout(animStep, 400); });
    cap.innerHTML = '<b style="color:var(--text)">Year by year:</b> each frame is one year, 1981-2025, compared with the 1981-2010 average of the same grid cell.';
  } else {
    const f = FIGS['map_' + v]; Plotly.newPlot('fig-map', f.data, f.layout, CONFIG);
    const k = FACTS['map_' + v];
    cap.innerHTML = `<b style="color:var(--text)">${k.label}</b>: Mongolia average ${k.avg} per decade (${k.verdict}). ` +
      `Increase over ${k.up}% of the area (${k.up_bh}% after correction), decrease over ${k.down}% (${k.down_bh}%). Dots = p < 0.05 before correction.`;
  }
  document.querySelectorAll('#map-btns .btn').forEach(b => b.classList.toggle('on', b.dataset.v === v));
}
function showScan(site) {
  const s = SCANS[site];
  document.getElementById('scan-title').innerHTML = `<b>${site}</b>: ${s.n_sig} of ${s.n} variables have a significant trend <span class="muted">· top 8 shown</span>`;
  document.getElementById('scan-body').innerHTML = s.rows;
  document.querySelectorAll('#scan-btns .btn').forEach(b => b.classList.toggle('on', b.dataset.site === site));
}
document.querySelectorAll('#map-btns .btn').forEach(b => b.onclick = () => showMap(b.dataset.v));
document.querySelectorAll('#scan-btns .btn').forEach(b => b.onclick = () => showScan(b.dataset.site));
showMap('T2M'); showScan(Object.keys(SCANS)[1] || Object.keys(SCANS)[0]);

// ---------- slide 6: seasons / Arctic toggle ----------
function showFind(k) {
  const f = FIGS[k]; Plotly.newPlot('fig-find', f.data, f.layout, CONFIG);
  document.getElementById('find-caption').innerHTML = FACTS[k + '_caption'];
  document.querySelectorAll('#find-btns .btn').forEach(b => b.classList.toggle('on', b.dataset.fig === k));
}
document.querySelectorAll('#find-btns .btn').forEach(b => b.onclick = () => showFind(b.dataset.fig));
showFind('seasons');

// ---------- slide 5: timeline scan line, count-up numbers, stripe tooltip ----------
const scanEl = document.getElementById('scan'), readout = document.getElementById('readout');
let scanRAF = null;
function runTimeline() {
  cancelAnimationFrame(scanRAF);
  const n = STRIPES.length, t0 = performance.now() + 1150, dur = 2600;
  document.querySelectorAll('.pin').forEach(p => { p.style.transition = 'none'; p.style.opacity = 0; });
  scanEl.style.opacity = 0; readout.style.opacity = 0;
  const tick = now => {
    const p = Math.min(1, Math.max(0, (now - t0) / dur)), e = p < .5 ? 2*p*p : 1 - Math.pow(-2*p + 2, 2) / 2;
    if (now >= t0) {
      const x = BAND.x + e * BAND.w, i = Math.min(n - 1, Math.floor(e * n)), st = STRIPES[i];
      scanEl.style.left = x + 'px'; scanEl.style.opacity = p < 1 ? 1 : 0;
      readout.style.left = x + 'px'; readout.style.opacity = p < 1 ? 1 : 0;
      readout.innerHTML = `${st.y} <span style="color:${st.a > 0 ? 'var(--hot)' : 'var(--cool)'}">${st.a > 0 ? '+' : ''}${st.a.toFixed(2)} °C</span>`;
    }
    if (p < 1) scanRAF = requestAnimationFrame(tick);
    else document.querySelectorAll('.pin').forEach((pin, k) => setTimeout(() => { pin.style.transition = 'opacity .5s'; pin.style.opacity = 1; }, k * 180));
  };
  scanRAF = requestAnimationFrame(tick);
}
function countUp(root) {
  root.querySelectorAll('[data-count]').forEach(el => {
    const target = parseFloat(el.dataset.count), dec = +el.dataset.dec, pre = el.dataset.prefix || '', suf = el.dataset.suffix || '';
    const host = el.closest('[data-a]'), delay = host ? parseFloat(getComputedStyle(host).getPropertyValue('--d')) || 0 : 0;
    const t0 = performance.now() + delay, dur = 1500;
    const step = now => { const p = Math.min(1, Math.max(0, (now - t0) / dur)), e = 1 - Math.pow(1 - p, 3), v = target * e;
      el.textContent = (v >= 0 && pre ? pre : '') + v.toFixed(dec) + suf; if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  });
}
const stripesEl = document.getElementById('stripes'), tip = document.getElementById('tip');
stripesEl.addEventListener('mousemove', e => {
  if (cur !== 4) return;
  const r = stripesEl.getBoundingClientRect();
  const i = Math.min(STRIPES.length - 1, Math.max(0, Math.floor((e.clientX - r.left) / r.width * STRIPES.length)));
  const st = STRIPES[i], sr = stage.getBoundingClientRect(), k = sr.width / 1920;
  tip.innerHTML = `<b>${st.y}</b> · ${st.a > 0 ? '+' : ''}${st.a.toFixed(2)} °C vs 1981-2010`;
  tip.style.left = ((e.clientX - sr.left) / k + 14) + 'px'; tip.style.top = ((e.clientY - sr.top) / k - 46) + 'px'; tip.style.opacity = 1;
});
stripesEl.addEventListener('mouseleave', () => tip.style.opacity = 0);

// ---------- navigation ----------
const slides = [...document.querySelectorAll('.slide')], dots = document.getElementById('dots');
slides.forEach((s, i) => { const d = document.createElement('button'); d.className = 'dot'; d.title = s.dataset.title;
  d.setAttribute('aria-label', 'Slide ' + (i+1)); d.onclick = () => go(i); dots.appendChild(d); });
function go(i) {
  i = Math.max(0, Math.min(slides.length - 1, i)); if (i === cur) return;
  stage.style.setProperty('--dir', i > cur ? 1 : -1);
  stage.classList.toggle('from-title', cur === 0 && i > 0);
  if (cur >= 0) { const old = slides[cur]; old.classList.remove('active'); old.classList.add('leaving'); setTimeout(() => old.classList.remove('leaving'), 420); }
  cur = i; stage.dataset.s = i + 1; tip.style.opacity = 0;
  const s = slides[cur]; s.classList.remove('leaving'); void s.offsetWidth; s.classList.add('active');
  [...dots.children].forEach((d, j) => d.classList.toggle('on', j === cur));
  document.getElementById('count').textContent = `${cur+1} / ${slides.length}`;
  document.getElementById('progress').style.width = `${(cur+1)/slides.length*100}%`;
  document.getElementById('prev').disabled = cur === 0; document.getElementById('next').disabled = cur === slides.length - 1;
  history.replaceState(null, '', '#' + (cur+1));
  stopAnim(); if (cur === 3 && mapView === 'anim') animTimer = setTimeout(animStep, 500);
  if (cur === 4) { runTimeline(); countUp(s); } else { cancelAnimationFrame(scanRAF); scanEl.style.opacity = 0; readout.style.opacity = 0; }
  s.querySelectorAll('.js-plotly-plot').forEach(gd => Plotly.Plots.resize(gd));
}
document.getElementById('prev').onclick = () => go(cur - 1);
document.getElementById('next').onclick = () => go(cur + 1);
addEventListener('keydown', e => {
  if (['ArrowRight','PageDown',' '].includes(e.key)) { e.preventDefault(); go(cur + 1); }
  if (['ArrowLeft','PageUp'].includes(e.key)) { e.preventDefault(); go(cur - 1); }
  if (e.key === 'Home') go(0); if (e.key === 'End') go(slides.length - 1);
});
let tx = null;
addEventListener('touchstart', e => { tx = e.touches[0].clientX; }, {passive:true});
addEventListener('touchend', e => { if (tx === null) return; const dx = e.changedTouches[0].clientX - tx;
  if (Math.abs(dx) > 50) go(cur + (dx < 0 ? 1 : -1)); tx = null; });
go((parseInt(location.hash.slice(1)) || 1) - 1);
});
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-url", default="")
    args = ap.parse_args()
    figs, facts, scans, stripes = build_data()
    t, s, c = facts["t2m"], facts["seasons"], facts["compare"]
    facts["seasons_caption"] = (f"<b style='color:var(--text)'>Temperature trend by season:</b> summers warm significantly at "
                                f"{s['summer_sig']} of {s['n']} sites; winters lean colder (average {s['winter_avg']:+.2f} °C per decade), "
                                f"significant at {'none' if s['winter_sig'] == 0 else s['winter_sig']} of the {s['n']}. Faded bars are not significant. Hover the bars.")
    facts["compare_caption"] = (f"<b style='color:var(--text)'>Opposite trends:</b> Svalbard winters (one Arctic grid point) warmed "
                                f"{c['arctic']:+.2f} °C per decade (Mann-Kendall p = {format_p(c['arctic_p'])}) while Ulaanbaatar winters "
                                f"lean {c['ub']:+.2f} °C ({c['ub_verdict']}). Lines show each place's difference from its own average.")

    n = len(stripes)
    sx, sy = BAND["w"] / 1920, BAND["h"] / 1080
    x_of = lambda i: BAND["x"] + (i + 0.5) * BAND["w"] / n  # noqa: E731
    stripes_html = "".join(f'<i style="background:{st["c"]}"></i>' for st in stripes)
    pins = "".join(
        f'<div class="pin" style="left:{x_of(p["i"]):.1f}px; top:{BAND["y"] - 86}px; opacity:0;"><div class="t">{html.escape(p["label"])}</div>'
        f'<div class="v" style="color:{"var(--hot)" if p["val"].startswith("+") else "var(--cool)"}">{html.escape(p["val"])}</div><div class="stem"></div></div>'
        for p in facts["pins"])
    year_idx = {st["y"]: i for i, st in enumerate(stripes)}
    years = "".join(f'<div class="yr" data-a="fade" style="left:{x_of(year_idx[y]):.1f}px; --d:1300">{y}</div>'
                    for y in (1981, 1990, 2000, 2010, 2025) if y in year_idx)

    if args.app_url:
        url = html.escape(args.app_url)
        app_link, app_cta = f'<a href="{url}">Open the live app ↗</a>', f'<a class="cta" href="{url}">Open the live app ↗</a>'
    else:
        app_link, app_cta = "", '<p class="muted" style="font-size:25px;">Live app link: see the project page.</p>'

    reps = {
        "__FIGS__": json.dumps(figs, separators=(",", ":")),
        "__FACTS__": json.dumps(facts, separators=(",", ":"), default=float),
        "__SCANS__": json.dumps(scans, separators=(",", ":"), ensure_ascii=False),
        "__STRIPES_JSON__": json.dumps(stripes, separators=(",", ":")),
        "__BAND__": json.dumps(BAND),
        "__STRIPES__": stripes_html, "__PINS__": pins, "__YEARS__": years,
        "__BX__": str(BAND["x"]), "__BY__": str(BAND["y"]), "__BH__": str(BAND["h"]),
        "__SX__": f"{sx:.5f}", "__SY__": f"{sy:.5f}",
        "__MAP_BUTTONS__": "".join(f'<button class="btn" data-v="{v}">{html.escape(C.VARIABLES[v]["label"])}</button>' for v in MAP_VARS),
        "__SCAN_BUTTONS__": "".join(f'<button class="btn" data-site="{html.escape(k)}">{html.escape(k)}</button>' for k in scans),
        "__T2M_RATE__": f"{t['rate']:.4f}", "__T2M_P__": format_p(t["p"]),
        "__WARM__": f"{t['warm']:.0f}", "__COOL__": f"{t['cool']:.0f}", "__WARM_BH__": f"{t['warm_bh']:.0f}", "__CELLS__": str(t["cells"]),
        "__T2M_RATE_TXT__": f"{t['rate']:+.2f} °C", "__WIND_RATE_TXT__": f"{facts['wind']['rate']:.2f} m/s",
        "__WIND_RATE__": f"{facts['wind']['rate']:.4f}", "__WIND_VERDICT__": facts["wind"]["verdict"],
        "__SUMMER_SIG__": str(s["summer_sig"]), "__NSITES__": str(s["n"]), "__WINTER_AVG__": f"{s['winter_avg']:+.2f}",
        "__ARCTIC__": f"{c['arctic']:+.2f}",
        "__APP_LINK__": app_link, "__APP_CTA__": app_cta, "__PDF_URL__": PDF_URL, "__REPO__": REPO,
    }
    page = PAGE
    for k, v in reps.items():
        page = page.replace(k, v)
    left = set(re.findall(r"__[A-Z0-9_]+__", page))
    assert not left, f"unfilled placeholders: {left}"

    (DOCS / "slides").mkdir(parents=True, exist_ok=True)
    (DOCS / "img").mkdir(exist_ok=True)
    (DOCS / "slides" / "index.html").write_text(page)
    (DOCS / ".nojekyll").write_text("")
    shutil.copy(ROOT / "demo" / "img" / "app.png", DOCS / "img" / "app.png")
    shutil.copy(Path(plotly.__file__).parent / "package_data" / "plotly.min.js", DOCS / "plotly.min.js")
    print(f"wrote docs/slides/index.html ({(DOCS / 'slides' / 'index.html').stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
