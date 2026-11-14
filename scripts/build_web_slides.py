"""Build the interactive 7-slide web presentation (docs/index.html) for GitHub Pages.

    python3 scripts/build_web_slides.py                          # GitHub link only
    python3 scripts/build_web_slides.py --app-url https://...    # also link the live app

Every chart is a live Plotly figure made by trend_detective.figures from the bundled NASA POWER data,
so the slides show exactly what the app computes. Plotly.js is copied next to the page (no CDN needed).

AI disclosure: written with help from Claude Code (Anthropic's AI coding assistant). See README, "Use of AI".
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly
import plotly.io as pio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trend_detective import catalog as C  # noqa: E402
from trend_detective.analysis import analyze, format_num, format_p, grid_trends  # noqa: E402
from trend_detective.data import country_average, load_boundary, load_grid, load_point, seasonal_series  # noqa: E402
from trend_detective.figures import (  # noqa: E402
    anomaly_animation, compare_figure, map_figure, seasons_figure, slide_style, trend_figure,
)

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO = "https://github.com/SigmabishrelXx/earth-system-trend-detective"
PDF_URL = f"{REPO}/blob/main/demo/Earth_System_Trend_Detective_slides.pdf"
MAP_VARS = ["T2M", "WS2M", "PRECTOTCORR", "GWETROOT", "FROST_DAYS", "SNODP"]
Y0, Y1 = C.START_YEAR, C.END_YEAR


def fig_json(fig) -> dict:
    return json.loads(pio.to_json(fig, validate=False))


def area_share(tr: pd.DataFrame, mask) -> float:
    w = np.cos(np.radians(tr["Lat"]))
    return float(w[mask].sum() / w.sum() * 100)


def verdict_icon(r) -> str:
    return {"significant": "✅", "mixed": "⚠️", "not significant": "➖"}[r.verdict]


def build_data():
    grid = load_grid()
    boundary = load_boundary()
    figs, facts = {}, {}

    # Slide 1: animated year-by-year temperature anomaly (no controls; the page loops it)
    gv = grid[(grid["Variable"] == "T2M") & grid["InMongolia"]]
    anim = anomaly_animation(gv, "T2M", boundary, height=640)
    anim.layout.sliders = ()
    anim.layout.updatemenus = ()
    anim.update_layout(showlegend=False, margin=dict(l=0, r=0, t=56, b=0))
    anim.update_xaxes(visible=False)
    anim.update_yaxes(visible=False)
    figs["anim"] = slide_style(anim, font_size=20)

    # Slide 4: trend maps for several variables (switchable)
    for var in MAP_VARS:
        sub = grid[(grid["Variable"] == var) & grid["InMongolia"]]
        tr = grid_trends(sub, Y0, Y1)
        nat = analyze(country_average(grid, var))
        sig = tr["PMK"] < 0.05
        facts[f"map_{var}"] = {
            "label": C.VARIABLES[var]["label"], "unit": C.VARIABLES[var]["unit"],
            "avg": format_num(nat.per_decade, C.VARIABLES[var]["unit"]), "verdict": nat.verdict,
            "up": round(area_share(tr, sig & (tr["PerDecade"] > 0))), "down": round(area_share(tr, sig & (tr["PerDecade"] < 0))),
        }
        f = map_figure(tr, var, boundary, height=600)
        f.update_layout(margin=dict(l=0, r=0, t=36, b=0))
        figs[f"map_{var}"] = slide_style(f, font_size=16)
        if var == "T2M":
            facts["t2m"] = {"per_decade": nat.per_decade, "p": nat.mk.p, "total": nat.total_change,
                            "warm_share": area_share(tr, sig & (tr["PerDecade"] > 0)),
                            "cool_share": area_share(tr, sig & (tr["PerDecade"] < 0))}
            fig = trend_figure(country_average(grid, var), nat, var, "", height=470)
            fig.update_layout(title=None, margin=dict(l=10, r=10, t=40, b=10))
            figs["trend"] = slide_style(fig, font_size=17)
        if var == "WS2M":
            facts["wind"] = {"per_decade": nat.per_decade, "p": nat.mk.p, "verdict": nat.verdict}

    # Slide 4: "what is changing" scanner tables for the Mongolian sites
    scans = {}
    seasons_rows = []
    for site in C.MONGOLIA_SITES:
        lat, lon, _ = C.LOCATIONS[site]
        monthly, _ = load_point(lat, lon)
        rows = []
        for var in C.VARIABLES:
            s = seasonal_series(monthly, var, "Whole year")
            if len(s) < 5 or s["Value"].std() == 0:
                continue
            r = analyze(s)
            rows.append((var, r))
        order = {"significant": 0, "mixed": 1, "not significant": 2}
        rows.sort(key=lambda t: (order[t[1].verdict], -abs(t[1].mk.z)))
        n_sig = sum(r.verdict == "significant" for _, r in rows)
        body = "".join(
            f'<tr class="{r.verdict.replace(" ", "-")}"><td>{verdict_icon(r)}</td><td>{html.escape(C.VARIABLES[v]["label"])}</td>'
            f'<td class="r">{html.escape(format_num(r.per_decade, C.VARIABLES[v]["unit"]))}</td>'
            f'<td class="r">{"↑" if r.slope > 0 else "↓"}</td><td class="r">{html.escape(format_p(r.mk.p))}</td></tr>'
            for v, r in rows[:8])
        scans[site.split(" (")[0]] = {"n_sig": n_sig, "n": len(rows), "rows": body}
        for season in list(C.SEASONS)[1:]:
            r = analyze(seasonal_series(monthly, "T2M", season))
            seasons_rows.append((site.split(" (")[0], season.split(" ")[0].lower(), r.per_decade, r.verdict == "significant"))
    sdf = pd.DataFrame(seasons_rows, columns=["Site", "Season", "PerDecade", "Significant"])
    figs["seasons"] = slide_style(seasons_figure(sdf, height=520), font_size=17)
    summer = sdf[sdf["Season"] == "summer"]
    winter = sdf[sdf["Season"] == "winter"]
    facts["seasons"] = {"summer_sig": int(summer["Significant"].sum()), "n": len(summer),
                        "winter_sig": int(winter["Significant"].sum()), "winter_avg": winter["PerDecade"].mean()}

    # Slide 6: warm Arctic vs Ulaanbaatar winters
    def winter(name):
        lat, lon, _ = C.LOCATIONS[name]
        s = seasonal_series(load_point(lat, lon)[0], "T2M", "Winter (Dec-Feb)")
        return s, analyze(s)
    a, ra = winter("Ulaanbaatar (capital)")
    b, rb = winter("Arctic (Svalbard, Norway)")
    cf = compare_figure(a, ra, "Ulaanbaatar", b, rb, "Svalbard (Arctic)", "T2M", height=520)
    cf.update_layout(title=None, margin=dict(l=10, r=10, t=40, b=10))
    figs["compare"] = slide_style(cf, font_size=17)
    facts["compare"] = {"ub": ra.per_decade, "ub_verdict": ra.verdict, "arctic": rb.per_decade, "arctic_p": rb.mk.p}
    return {k: fig_json(v) for k, v in figs.items()}, facts, scans


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Earth System Trend Detective · Team Florensiza · NASA Space Apps 2026</title>
<meta name="description" content="Interactive 7-slide demo for the NASA Space Apps Challenge 2026 challenge Be An Earth System Trend Detective! by Team Florensiza (Bishrel), Ulaanbaatar. Made with help from Claude Code (AI).">
<meta name="author" content="Bishrel (Team Florensiza)">
<script src="plotly.min.js"></script>
<style>
  :root { --bg:#0b0f17; --panel:#121826; --line:#243045; --text:#e8edf5; --muted:#93a1b8; --hot:#ff6b4a; --cool:#4d9fff; --teal:#2dd4bf; --gold:#fbbf24; }
  * { box-sizing:border-box; margin:0; padding:0; }
  html, body { height:100%; background:var(--bg); color:var(--text); overflow:hidden;
               font-family:-apple-system,"SF Pro Display","Helvetica Neue",Arial,sans-serif; }
  #viewport { position:fixed; inset:0; display:flex; align-items:center; justify-content:center; }
  #stage { width:1920px; height:1080px; position:relative; transform-origin:center center; flex:none; }
  .slide { position:absolute; inset:0; padding:76px 104px 96px; display:flex; flex-direction:column;
           opacity:0; visibility:hidden; transition:opacity .45s ease, transform .45s ease; transform:translateX(40px);
           background: radial-gradient(1100px 700px at 100% 0%, rgba(255,107,74,.10), transparent 60%),
                       radial-gradient(900px 600px at 0% 100%, rgba(45,212,191,.07), transparent 60%), var(--bg); }
  .slide.active { opacity:1; visibility:visible; transform:none; }
  .slide.past { transform:translateX(-40px); }
  .kicker { font-size:22px; letter-spacing:.16em; text-transform:uppercase; color:var(--hot); font-weight:700; }
  h1 { font-size:100px; line-height:1; font-weight:800; letter-spacing:-.02em; }
  h2 { font-size:60px; line-height:1.08; font-weight:800; letter-spacing:-.015em; margin-top:12px; }
  h3 { font-size:34px; font-weight:700; margin-bottom:10px; }
  p, li { font-size:30px; line-height:1.38; }
  .muted { color:var(--muted); } .hot { color:var(--hot); } .cool { color:var(--cool); } .teal { color:var(--teal); } .gold { color:var(--gold); }
  .grid { display:grid; gap:44px; flex:1; min-height:0; margin-top:36px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:22px; padding:30px 34px; }
  .card p { font-size:27px; }
  ul.clean { list-style:none; } ul.clean li { padding-left:46px; position:relative; margin-bottom:26px; font-size:33px; }
  ul.clean li::before { content:""; position:absolute; left:0; top:15px; width:22px; height:22px; border-radius:6px; background:var(--hot); }
  ul.clean.teal li::before { background:var(--teal); }
  .num { display:inline-flex; width:54px; height:54px; border-radius:50%; align-items:center; justify-content:center;
         background:var(--hot); color:#0b0f17; font-weight:800; font-size:28px; flex:none; }
  .step { display:flex; gap:22px; align-items:flex-start; margin-bottom:26px; padding:14px 16px; border-radius:16px;
          border:1px solid transparent; transition:background .2s, border-color .2s; cursor:default; }
  .step:hover { background:var(--panel); border-color:var(--line); }
  .step b { display:block; font-size:31px; margin-bottom:4px; } .step span { font-size:25px; line-height:1.35; color:var(--muted); }
  .chart { width:100%; }
  .btns { display:flex; flex-wrap:wrap; gap:10px; margin:6px 0 14px; }
  .btn { font:inherit; font-size:22px; padding:9px 18px; border-radius:999px; border:1px solid var(--line); background:var(--panel);
         color:var(--muted); cursor:pointer; transition:all .15s; }
  .btn:hover { color:var(--text); border-color:#3a4a66; } .btn.on { background:var(--hot); color:#0b0f17; border-color:var(--hot); font-weight:700; }
  .stat .big { font-size:80px; font-weight:800; line-height:1; letter-spacing:-.02em; }
  .stat .lbl { font-size:26px; color:var(--muted); margin-top:8px; line-height:1.3; } .stat { margin-bottom:30px; }
  .caption { font-size:22px; color:var(--muted); margin-top:10px; line-height:1.35; }
  .hint { font-size:20px; color:var(--muted); }
  table.scan { width:100%; border-collapse:collapse; font-size:23px; }
  table.scan td { padding:9px 12px; border-bottom:1px solid var(--line); } table.scan td.r { text-align:right; white-space:nowrap; }
  table.scan tr.significant td { color:var(--text); } table.scan tr.mixed td, table.scan tr.not-significant td { color:var(--muted); }
  table.scan th { text-align:left; font-size:19px; color:var(--muted); font-weight:600; padding:6px 12px; border-bottom:1px solid var(--line); }
  .shot { width:100%; border-radius:18px; border:1px solid var(--line); box-shadow:0 30px 80px rgba(0,0,0,.55); display:block; }
  a { color:var(--teal); text-decoration:none; } a:hover { text-decoration:underline; }
  .cta { display:inline-block; margin-top:14px; padding:14px 26px; border-radius:14px; background:var(--hot); color:#0b0f17 !important;
         font-weight:800; font-size:27px; text-decoration:none !important; }
  /* navigation */
  #nav { position:fixed; left:0; right:0; bottom:0; display:flex; align-items:center; justify-content:center; gap:16px;
         padding:10px; z-index:10; pointer-events:none; }
  #nav > * { pointer-events:auto; }
  .navbtn { width:44px; height:44px; border-radius:50%; border:1px solid var(--line); background:rgba(18,24,38,.85); color:var(--text);
            font-size:22px; cursor:pointer; }
  .navbtn:disabled { opacity:.35; cursor:default; }
  #dots { display:flex; gap:8px; } .dot { width:10px; height:10px; border-radius:50%; background:#334155; cursor:pointer; border:none; }
  .dot.on { background:var(--hot); width:26px; border-radius:6px; }
  #count { font-size:14px; color:var(--muted); min-width:48px; text-align:center; }
  #progress { position:fixed; top:0; left:0; height:3px; background:var(--hot); transition:width .35s; z-index:11; }
  #help { position:fixed; top:10px; right:14px; font-size:13px; color:var(--muted); z-index:11; }
  #help a { margin-left:12px; }
</style>
</head>
<body>
<div id="progress"></div>
<div id="help">← → keys or swipe to move · <a href="__PDF_URL__">PDF version</a></div>
<div id="viewport"><div id="stage">

<!-- 1 -->
<section class="slide" data-title="Title">
  <div style="display:grid; grid-template-columns: 0.9fr 1.1fr; gap:40px; flex:1; align-items:center;">
    <div>
      <div class="kicker">NASA Space Apps Challenge 2026</div>
      <p class="muted" style="margin-top:12px;">Challenge: <b style="color:var(--text)">Be An Earth System Trend Detective!</b></p>
      <h1 style="margin-top:44px;">Earth System<br>Trend <span class="hot">Detective</span></h1>
      <p style="font-size:38px; margin-top:32px; line-height:1.3;">What is changing, where, by how much,<br>and is it <span class="hot">really</span> changing?</p>
      <div style="margin-top:56px; font-size:30px; line-height:1.6;">
        <div><span class="muted">Team</span> <b>Florensiza</b></div>
        <div><span class="muted">Member</span> <b>Bishrel</b></div>
        <div><span class="muted">Local event</span> <b>Ulaanbaatar, Mongolia</b></div>
      </div>
    </div>
    <div>
      <div id="fig-anim" class="chart" style="height:640px;"></div>
      <div class="caption" style="text-align:center;">Every year since 1981, compared with the 1981-2010 average (NASA POWER / MERRA-2). Hover any cell.</div>
    </div>
  </div>
</section>

<!-- 2 -->
<section class="slide" data-title="The case">
  <div class="kicker">The case</div>
  <h2>Is Mongolia's climate really changing?<br><span class="muted" style="font-weight:700;">Finding out is harder than it sounds.</span></h2>
  <div class="grid" style="grid-template-columns:1fr 1fr;">
    <div class="card">
      <h3 class="hot" style="font-size:40px;">Why it's hard</h3>
      <ul class="clean" style="margin-top:24px;">
        <li>Hundreds of Earth variables. <b>Which ones</b> are changing?</li>
        <li>One process can push a variable <b>up in one region and down in another</b>.</li>
        <li>A few warm years can look like a trend. Is it <b>statistically significant</b>, or chance?</li>
      </ul>
    </div>
    <div class="card">
      <h3 class="teal" style="font-size:40px;">Why it matters in Mongolia</h3>
      <ul class="clean teal" style="margin-top:24px;">
        <li><b>Dzud</b>: harsh winters after dry summers can kill millions of livestock.</li>
        <li><b>Desertification</b> and dust storms in the Gobi.</li>
        <li><b>Permafrost thaw</b> in the north.</li>
      </ul>
      <p class="muted" style="font-size:29px; margin-top:12px;">Herders, students and cities need evidence, not guesses.</p>
    </div>
  </div>
  <p style="margin-top:30px; font-size:28px;"><span class="muted">Built for:</span> high-school and university students, and curious citizens. No coding needed.</p>
</section>

<!-- 3 -->
<section class="slide" data-title="How it works">
  <div class="kicker">How it works</div>
  <h2>Pick a variable. Pick a place. Get a verdict.</h2>
  <div class="grid" style="grid-template-columns:1.3fr 1fr; align-items:start;">
    <div>
      <img src="img/app.png" class="shot" alt="The Earth System Trend Detective app">
      <div class="caption">The real app: demo mission 1 asks students to guess first, then shows the evidence. __APP_LINK__</div>
    </div>
    <div>
      <div class="step"><div class="num">1</div><div><b>What?</b><span>14 NASA variables, from temperature and frost days to soil moisture, snow, wind and sunlight. Each with a simple definition.</span></div></div>
      <div class="step"><div class="num">2</div><div><b>Where?</b><span>Any point on Earth, 5 Mongolian regions, or all of Mongolia (587 grid cells). Click the map to explore any cell.</span></div></div>
      <div class="step"><div class="num">3</div><div><b>When?</b><span>Whole year or one season, any years 1981-2025. Watch the map change year by year.</span></div></div>
      <div class="step"><div class="num">4</div><div><b>Is it real?</b><span>t-test with 95% confidence interval, Mann-Kendall test and Sen's slope. "Significant" only when both agree.</span></div></div>
      <p class="hint" style="margin-top:4px;">Plus: 6 guided missions with a "guess first" game, compare two places, CSV download.</p>
    </div>
  </div>
</section>

<!-- 4 -->
<section class="slide" data-title="Where and what">
  <div class="kicker">Detective tools · try them</div>
  <h2>See <span class="hot">where</span> it is changing, and <span class="teal">what</span> is changing</h2>
  <div class="grid" style="grid-template-columns:1.18fr 1fr; align-items:start; margin-top:26px;">
    <div>
      <div class="btns" id="map-btns">__MAP_BUTTONS__</div>
      <div id="fig-map" class="chart" style="height:600px;"></div>
      <div class="caption" id="map-caption"></div>
    </div>
    <div>
      <div class="btns" id="scan-btns">__SCAN_BUTTONS__</div>
      <div class="card" style="padding:20px 24px;">
        <p style="font-size:24px; margin-bottom:10px;" id="scan-title"></p>
        <table class="scan"><thead><tr><th></th><th>Variable</th><th style="text-align:right">per decade</th><th></th><th style="text-align:right">MK p</th></tr></thead>
        <tbody id="scan-body"></tbody></table>
      </div>
      <div class="caption">The scanner tests all 14 variables at a place and ranks them by evidence. ✅ significant · ⚠️ tests disagree · ➖ not significant</div>
    </div>
  </div>
</section>

<!-- 5 -->
<section class="slide" data-title="NASA data">
  <div class="kicker">Powered by NASA open data</div>
  <h2>Real NASA data, real statistics, honest answers</h2>
  <div class="grid" style="grid-template-columns:1fr 1.2fr; align-items:start;">
    <div style="display:flex; flex-direction:column; gap:20px;">
      <div class="card"><h3 class="hot">NASA POWER <span class="muted" style="font-size:24px; font-weight:600;">· Langley Research Center</span></h3>
        <p>Monthly and yearly data, 1981-2025, for single points and a grid over Mongolia.</p></div>
      <div class="card"><h3 class="gold">MERRA-2 <span class="muted" style="font-size:24px; font-weight:600;">· NASA GMAO model</span></h3>
        <p>Temperature, frost days, rain, humidity, evaporation, soil moisture, snow, wind.</p></div>
      <div class="card"><h3 class="teal">CERES <span class="muted" style="font-size:24px; font-weight:600;">· NASA satellites</span></h3>
        <p>Sunlight reaching the ground and cloud cover.</p></div>
    </div>
    <div>
      <div id="fig-trend" class="chart" style="height:470px;"></div>
      <div class="caption"><b style="color:var(--text)">Mongolia average air temperature, 1981-2025.</b> Hover for each year; click "Sen's slope" in the legend to compare the robust trend line.</div>
      <ul class="clean teal" style="margin-top:22px;">
        <li style="font-size:25px; margin-bottom:10px;">Never invents data: a real NASA snapshot ships with the app for slow Wi-Fi.</li>
        <li style="font-size:25px; margin-bottom:10px;">Warns about data-source changes and correlated years. 20 automated tests check the maths.</li>
      </ul>
    </div>
  </div>
</section>

<!-- 6 -->
<section class="slide" data-title="Findings">
  <div class="kicker">What we found · NASA POWER, 1981-2025</div>
  <h2>Mongolia is warming, but not evenly</h2>
  <div class="grid" style="grid-template-columns:0.78fr 1.3fr; align-items:start;">
    <div style="padding-top:8px;">
      <div class="stat"><div class="big hot">__T2M_RATE__</div><div class="lbl">per decade, Mongolia average.<br>Significant (Mann-Kendall p = __T2M_P__).</div></div>
      <div class="stat"><div class="big hot">__WARM_SHARE__%</div><div class="lbl">of Mongolia's area is warming significantly.<br>__COOL_SHARE__% is cooling significantly.</div></div>
      <div class="stat"><div class="big teal">__WIND_RATE__</div><div class="lbl">per decade: winds are slowing<br>across Mongolia (__WIND_VERDICT__).</div></div>
    </div>
    <div>
      <div class="btns" id="find-btns">
        <button class="btn on" data-fig="seasons">Seasons at 5 sites</button>
        <button class="btn" data-fig="compare">Warm Arctic vs Ulaanbaatar</button>
      </div>
      <div id="fig-find" class="chart" style="height:520px;"></div>
      <div class="caption" id="find-caption"></div>
    </div>
  </div>
</section>

<!-- 7 -->
<section class="slide" data-title="Next">
  <div class="kicker">What's next</div>
  <h2>Every student can be a<br>climate trend detective</h2>
  <div class="grid" style="grid-template-columns:1.1fr 1fr; align-items:center;">
    <ul class="clean">
      <li><b>Mongolian-language version</b> for schools and herder communities.</li>
      <li><b>More NASA data:</b> GLDAS soil water and streamflow, MODIS vegetation greenness.</li>
      <li><b>Seasonal trend maps</b> and more classroom missions.</li>
      <li><b>Smarter tests</b> that correct for year-to-year memory.</li>
    </ul>
    <div class="card" style="padding:40px 44px;">
      <h3 style="font-size:40px;">Try it</h3>
      __APP_CTA__
      <p style="font-size:26px; margin-top:18px;"><span class="muted">Code:</span><br><a href="__REPO__">github.com/SigmabishrelXx/earth-system-trend-detective</a></p>
      <p style="font-size:24px; margin-top:18px;" class="muted">Teachers can share a ready-made mission: add <b style="color:var(--text)">?mission=3</b> to the app link. Open source, MIT License.</p>
    </div>
  </div>
  <p class="muted" style="font-size:20px; line-height:1.45; margin-top:20px;">
    Data: NASA Langley Research Center (LaRC) POWER Project. Starting code: kdmayer/nasa-power-api (MIT). NASA does not endorse this project.<br>
    AI use: the app's code and these slides were made with help from Claude Code (an AI assistant); every number comes from NASA data, computed by the app.</p>
</section>

</div></div>
<div id="nav">
  <button class="navbtn" id="prev" aria-label="Previous slide">‹</button>
  <div id="dots"></div><div id="count"></div>
  <button class="navbtn" id="next" aria-label="Next slide">›</button>
</div>

<script>
const FIGS = __FIGS__;
const FACTS = __FACTS__;
const SCANS = __SCANS__;
const CONFIG = {displaylogo:false, responsive:true, modeBarButtonsToRemove:['lasso2d','select2d','toImage']};

// ---------- stage scaling: always fit the 1920x1080 slide to the window ----------
const stage = document.getElementById('stage');
function fit() { const s = Math.min(innerWidth/1920, innerHeight/1080); stage.style.transform = `scale(${s})`; }
addEventListener('resize', fit); fit();

// ---------- charts ----------
function draw(id, key) { const f = FIGS[key]; return Plotly.react(id, f.data, f.layout, CONFIG); }

// Slide 1: looping animation
let animTimer = null, animIdx = 0;
const anim = FIGS.anim;
Plotly.newPlot('fig-anim', anim.data, anim.layout, {...CONFIG, displayModeBar:false}).then(gd => Plotly.addFrames(gd, anim.frames));
function animStep() {
  const frames = anim.frames; animIdx = (animIdx + 1) % frames.length;
  Plotly.animate('fig-anim', [frames[animIdx].name], {mode:'immediate', frame:{duration:0, redraw:true}, transition:{duration:0}});
  animTimer = setTimeout(animStep, animIdx === frames.length - 1 ? 2200 : 330);
}

// Slide 4: map switcher + scanner
function showMap(v) {
  draw('fig-map', 'map_' + v);
  const f = FACTS['map_' + v];
  document.getElementById('map-caption').innerHTML =
    `<b style="color:var(--text)">${f.label}</b>: Mongolia average ${f.avg} per decade (${f.verdict}). ` +
    `Significant increase over ${f.up}% of the area, decrease over ${f.down}%. Dots = significant cells. Hover any cell.`;
  document.querySelectorAll('#map-btns .btn').forEach(b => b.classList.toggle('on', b.dataset.v === v));
}
function showScan(site) {
  const s = SCANS[site];
  document.getElementById('scan-title').innerHTML = `<b>${site}</b>: ${s.n_sig} of ${s.n} variables have a significant trend`;
  document.getElementById('scan-body').innerHTML = s.rows;
  document.querySelectorAll('#scan-btns .btn').forEach(b => b.classList.toggle('on', b.dataset.site === site));
}
document.querySelectorAll('#map-btns .btn').forEach(b => b.onclick = () => showMap(b.dataset.v));
document.querySelectorAll('#scan-btns .btn').forEach(b => b.onclick = () => showScan(b.dataset.site));
showMap('T2M'); showScan(Object.keys(SCANS)[1] || Object.keys(SCANS)[0]);

// Slide 5 + 6
draw('fig-trend', 'trend');
const findCaptions = {
  seasons: FACTS.seasons_caption,
  compare: FACTS.compare_caption,
};
function showFind(k) {
  draw('fig-find', k);
  document.getElementById('find-caption').innerHTML = findCaptions[k];
  document.querySelectorAll('#find-btns .btn').forEach(b => b.classList.toggle('on', b.dataset.fig === k));
}
document.querySelectorAll('#find-btns .btn').forEach(b => b.onclick = () => showFind(b.dataset.fig));
showFind('seasons');

// ---------- navigation ----------
const slides = [...document.querySelectorAll('.slide')];
const dots = document.getElementById('dots');
slides.forEach((s, i) => { const d = document.createElement('button'); d.className = 'dot'; d.title = s.dataset.title;
  d.setAttribute('aria-label', 'Slide ' + (i+1)); d.onclick = () => go(i); dots.appendChild(d); });
let cur = 0;
function go(i) {
  cur = Math.max(0, Math.min(slides.length - 1, i));
  slides.forEach((s, j) => { s.classList.toggle('active', j === cur); s.classList.toggle('past', j < cur); });
  [...dots.children].forEach((d, j) => d.classList.toggle('on', j === cur));
  document.getElementById('count').textContent = `${cur+1} / ${slides.length}`;
  document.getElementById('progress').style.width = `${(cur+1)/slides.length*100}%`;
  document.getElementById('prev').disabled = cur === 0; document.getElementById('next').disabled = cur === slides.length - 1;
  history.replaceState(null, '', '#' + (cur+1));
  clearTimeout(animTimer); if (cur === 0) animTimer = setTimeout(animStep, 600);
  slides[cur].querySelectorAll('.js-plotly-plot').forEach(gd => Plotly.Plots.resize(gd));
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
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-url", default="")
    args = ap.parse_args()
    figs, facts, scans = build_data()

    t = facts["t2m"]
    s = facts["seasons"]
    c = facts["compare"]
    facts["seasons_caption"] = (f"<b style='color:var(--text)'>Seasons tell different stories:</b> summers warm significantly at "
                                f"{s['summer_sig']} of {s['n']} sites; winters lean colder (average {s['winter_avg']:+.2f} °C per decade), "
                                f"significant at {s['winter_sig']} sites. Faded bars are not significant. Hover the bars.")
    facts["compare_caption"] = (f"<b style='color:var(--text)'>Opposite trends:</b> Arctic winters warmed {c['arctic']:+.2f} °C per decade "
                                f"(Mann-Kendall p = {format_p(c['arctic_p'])}) while Ulaanbaatar winters lean {c['ub']:+.2f} °C "
                                f"({c['ub_verdict']}). Opposite directions, but only the Arctic trend is significant, so the link is a lead, not proof. "
                                f"Lines show winter temperature minus each place's own average.")

    if args.app_url:
        url = html.escape(args.app_url)
        app_link = f'<a href="{url}">Open the live app ↗</a>'
        app_cta = f'<a class="cta" href="{url}">Open the live app ↗</a>'
    else:
        app_link = ""
        app_cta = '<p class="muted" style="font-size:26px;">Live app link: see the project page.</p>'

    map_buttons = "".join(f'<button class="btn" data-v="{v}">{html.escape(C.VARIABLES[v]["label"])}</button>' for v in MAP_VARS)
    scan_buttons = "".join(f'<button class="btn" data-site="{html.escape(k)}">{html.escape(k)}</button>' for k in scans)

    page = (PAGE
            .replace("__FIGS__", json.dumps(figs, separators=(",", ":")))
            .replace("__FACTS__", json.dumps(facts, separators=(",", ":"), default=float))
            .replace("__SCANS__", json.dumps(scans, separators=(",", ":"), ensure_ascii=False))
            .replace("__MAP_BUTTONS__", map_buttons)
            .replace("__SCAN_BUTTONS__", scan_buttons)
            .replace("__T2M_RATE__", f"{t['per_decade']:+.2f} °C")
            .replace("__T2M_P__", format_p(t["p"]))
            .replace("__WARM_SHARE__", f"{t['warm_share']:.0f}")
            .replace("__COOL_SHARE__", f"{t['cool_share']:.0f}")
            .replace("__WIND_RATE__", f"{facts['wind']['per_decade']:+.2f} m/s")
            .replace("__WIND_VERDICT__", facts["wind"]["verdict"])
            .replace("__APP_LINK__", app_link)
            .replace("__APP_CTA__", app_cta)
            .replace("__PDF_URL__", PDF_URL)
            .replace("__REPO__", REPO))
    import re
    left = set(re.findall(r"__[A-Z0-9_]+__", page))
    assert not left, f"unfilled placeholders: {left}"

    DOCS.mkdir(exist_ok=True)
    (DOCS / "img").mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(page)
    (DOCS / ".nojekyll").write_text("")
    shutil.copy(ROOT / "demo" / "img" / "app.png", DOCS / "img" / "app.png")
    shutil.copy(Path(plotly.__file__).parent / "package_data" / "plotly.min.js", DOCS / "plotly.min.js")
    size = sum(f.stat().st_size for f in DOCS.rglob("*") if f.is_file()) / 1e6
    print(f"wrote docs/index.html ({(DOCS / 'index.html').stat().st_size / 1e6:.2f} MB), docs total {size:.1f} MB")


if __name__ == "__main__":
    main()
