# 🔎 Earth System Trend Detective

**NASA Space Apps Challenge 2026 · Challenge: [Be An Earth System Trend Detective!](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/)**
**Team Florensiza · Local event: Ulaanbaatar, Mongolia**

An interactive web app that helps students and the public become *data detectives*: pick an Earth science
variable produced by NASA models or measured by NASA satellites, pick a place (or the whole of Mongolia),
and find out **what is changing, where it is changing, how much it is changing, and whether the change is
statistically significant.**

**Live app:** _add your Streamlit Community Cloud link here after deploying_
**Interactive demo slides (7):** https://sigmabishrelxx.github.io/earth-system-trend-detective/ (cinematic, live charts; storyboard: [demo/STORYBOARD.md](demo/STORYBOARD.md); PDF version: [demo/Earth_System_Trend_Detective_slides.pdf](demo/Earth_System_Trend_Detective_slides.pdf))

---

## What it does

| Challenge objective | How the app answers it |
| --- | --- |
| Identify variables that could show trends | 14 NASA POWER variables in three themes (temperature, water, air & energy), each with a plain-language definition and a "why it matters" note. The **What is changing?** tab tests every variable at once and ranks them by strength of evidence. |
| Acquire data for a region | 8 preset locations (5 in Mongolia, 3 global contrasts), any custom latitude/longitude worldwide (fetched live), and a **country average for all of Mongolia** built from every NASA POWER grid cell inside the border. |
| Generate and visualise a time series | Interactive Plotly charts of yearly or seasonal values from 1981 to 2025, with the trend line, its 95% confidence band and Sen's slope. |
| Rate of change and significance testing | Least-squares trend with a **t-test** and **95% confidence interval**, the **Mann-Kendall test** (with tie correction) and **Sen's slope**. A trend is called *significant* only when both tests agree at the 5% level. |
| Where is it changing? | The **map tab** computes a trend for each of the 587 grid cells inside Mongolia and dots the cells with significant trends. **Click any cell** to see its own time series and verdict, or press **Play** to watch Mongolia change year by year (difference from the 1981-2010 average). |
| One variable, opposite trends in two regions | **Compare** mode puts two places side by side and flags when their trends run in opposite directions. |

### Also included

- **Seasons:** winter, spring, summer or autumn, because a yearly average can hide opposite seasonal trends.
- **"Guess first" game:** in a mission, students predict the trend before the evidence appears, then get feedback.
- **Six guided demo missions** (for example *Summer vs winter in Ulaanbaatar* and *Warm Arctic, cold Mongolia?*).
  Each one sets up the app and asks the student questions. The app computes the answers. Share a mission
  directly by adding `?mission=1` ... `?mission=6` to the app link.
- **"Years needed" hint:** when a trend is not significant, the app estimates how long a record would be needed
  if the trend and noise continued.
- **Mongolia insights tab:** country-wide trends, a season-by-season temperature comparison for five Mongolian
  regions, and links to dzud, desertification and permafrost.
- **Honest data handling:** the app never invents data. It warns about the 2001 change of data source for
  sunlight and cloud cover, and about year-to-year autocorrelation.
- **CSV download** of every series and trend line.
- **Works offline for presets:** a snapshot of real NASA POWER data ships with the app, so the demo works on slow Wi-Fi.

## Data

| Source | Used for |
| --- | --- |
| [NASA POWER](https://power.larc.nasa.gov) monthly & annual API (v2.x), `RE` community | All data in the app |
| MERRA-2 reanalysis (NASA GMAO), via POWER | Temperature, frost days, precipitation (gauge-corrected), humidity, evaporation, soil moisture, snow depth, wind |
| CERES SYN1deg (2001+) and GEWEX SRB (1984-2000), via POWER | Sunlight at the surface, cloud cover |
| [Natural Earth](https://www.naturalearthdata.com) 1:50m countries (public domain) | Mongolia border for the map and country average |

**Bundled snapshot (`data/bundled/`, downloaded 2026-11-14):** the raw POWER responses for every preset location and
the yearly values for the Mongolia grid. Custom locations are always fetched live, and the sidebar button
**Get the latest data from NASA** re-downloads a preset live. To refresh the snapshot:

```bash
python3 scripts/build_bundled_data.py
```

## Run it on your computer

```bash
pip install -r requirements.txt
```

```bash
python3 -m streamlit run app.py
```

Run the tests (statistics, seasonal maths, map masking):

```bash
python3 -m unittest discover -s tests -v
```

## Deploy to Streamlit Community Cloud

1. Push this folder to a **public** GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub and click **Create app**.
3. Choose the repository, branch `main` and main file `app.py`, then click **Deploy**.

## Project structure

```
app.py                         Streamlit user interface (tabs, charts, missions)
trend_detective/catalog.py     Variables, definitions, locations, seasons
trend_detective/data.py        NASA POWER access, bundled snapshot, seasons, Mongolia grid + border mask
trend_detective/analysis.py    Linear trend + t-test + CI, Mann-Kendall, Sen's slope, grid trends
trend_detective/figures.py     Plotly charts shared by the app and the web slides (map, animation, trends)
scripts/build_bundled_data.py  Downloads the bundled NASA POWER snapshot
tests/test_analysis.py         Unit tests
demo/                          Demo slides (slides.html -> PDF), screenshots of the real app
scripts/build_slides.py        Renders the slides PDF with headless Chrome
scripts/build_web_slides.py    Builds the interactive web slides in docs/ (GitHub Pages)
docs/                          Interactive web slides (index.html + Plotly.js), served by GitHub Pages
.streamlit/config.toml         Dark theme for the app
scripts/capture_screenshots.py Captures the app screenshots used in the slides
data/bundled/                  NASA POWER snapshot + Mongolia border
main.py, src/power_api.py      Original daily-data downloader from kdmayer/nasa-power-api (kept as-is)
```

## Methods and limitations

- Yearly values are NASA POWER's annual values. Seasonal values combine monthly values (mean; maximum or minimum
  for temperature extremes; total for frost days). Winter = previous December + January + February.
- The Mongolia average weights each grid cell by its area (cosine of latitude).
- Trend tests look for steady (linear or monotonic) change only, and assume independent years.
- MERRA-2 grid cells are about 50 km wide: they describe a region, not one weather station.
- Testing many variables at once means about 1 in 20 can look significant by chance.
- Sunlight and cloud cover switch data source in 2001; test 2001-2025 separately before trusting their trends.

## Credits and license

- **Data acknowledgement:** "The data was obtained from the National Aeronautics and Space Administration (NASA)
  Langley Research Center (LaRC) Prediction of Worldwide Energy Resource (POWER) Project funded through the NASA
  Earth Science/Applied Science Program."
- **Starting code:** forked from [kdmayer/nasa-power-api](https://github.com/kdmayer/nasa-power-api) by Kevin Mayer
  (MIT License). The original downloader (`main.py`, `src/power_api.py`, `config.yaml`) is kept unchanged.
  The trend detective app, package, tests and data scripts are new work by Team Florensiza.
- **Border data:** Natural Earth (public domain).
- **Libraries:** Streamlit, Plotly, pandas, NumPy, SciPy, Requests.
- No NASA logos or insignia are used. NASA does not endorse this project.
- Released under the MIT License (see `LICENSE`).

### References

- NASA POWER Project. https://power.larc.nasa.gov
- Gelaro, R., et al. (2017). The Modern-Era Retrospective Analysis for Research and Applications, Version 2 (MERRA-2). *Journal of Climate*, 30(14), 5419-5454. https://doi.org/10.1175/JCLI-D-16-0758.1
- Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica*, 13(3), 245-259.
- Kendall, M. G. (1975). *Rank Correlation Methods* (4th ed.). Charles Griffin.
- Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *Journal of the American Statistical Association*, 63(324), 1379-1389.
- IPCC (2018). *Global Warming of 1.5 °C*, Chapter 1 (warming rate of about 0.2 °C per decade).

### Use of AI

This project was built with help from **Claude Code** (Anthropic's AI coding assistant), which Space Apps calls
"Super Intelligence (SI)". Bishrel (Team Florensiza) chose the challenge, the approach and the Mongolian focus and
built the first version of the app. The AI then reviewed it, wrote most of the new code (statistics, data layer,
map, missions), wrote the unit tests and documentation, made the demo slides from screenshots of the real app, and
helped draft the submission text. Every code file starts with an AI disclosure note, and every AI-assisted commit
carries a `Co-Authored-By: Claude` line. All data and every number come from NASA POWER and are computed by the
app; the AI did not generate any data, images or results.
