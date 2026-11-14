# Space Apps 2026 submission text (Team Florensiza)

The sections below match the boxes on the Space Apps project page, in the same order
(from the official Project Submission Guide). All numbers come from the app (NASA POWER, 1981-2025).
Before submitting, replace the one ⟨live app link⟩ placeholder once the app is deployed.

---

## Project Name

Earth System Trend Detective

## High-Level Project Summary

Earth System Trend Detective is a free web app that turns 45 years of NASA Earth data into clear answers to four
questions: what is changing, where, by how much, and is the change significant? Users pick one of 14 NASA POWER
variables (from air temperature and frost days to soil moisture, snow depth, wind and sunlight, produced by the
MERRA-2 model and CERES satellite instruments, 1981-2025) and a place: any point on Earth, five Mongolian regions,
global contrasts, or the whole of Mongolia averaged from 587 grid cells. The app charts the yearly or seasonal
time series and runs a t-test with a 95% confidence interval, the Mann-Kendall test and Sen's slope, then explains
the verdict in plain language. A scanner ranks every variable by strength of evidence, a map shows where trends are
significant across Mongolia, and a compare mode reveals opposite trends in different regions. Six guided missions
teach students to think like detectives. Example finding: averaged over Mongolia, air temperature rose 0.18 °C per
decade (significant), with significant warming across 62% of the country, and summers are warming while winters are not.

## Link to Project Demo

https://sigmabishrelxx.github.io/earth-system-trend-detective/

(Interactive 7-slide web presentation with live charts, publicly viewable without login. Use the arrow keys or the
buttons to move. A PDF version is linked at the top of the page and is also at
https://github.com/SigmabishrelXx/earth-system-trend-detective/blob/main/demo/Earth_System_Trend_Detective_slides.pdf)

## Link to Final Project

⟨live app link⟩

Code: https://github.com/SigmabishrelXx/earth-system-trend-detective

## Detailed Project Description

**What it does.** The challenge asks for a tool that selects Earth science variables, visualises how they change
over time, and determines what is changing, where, how much, and whether the change is significant. Earth System
Trend Detective does all of this in one browser page, with no installation or login.

1. **Choose a variable (what).** 14 variables in three themes: temperature (air temperature, hottest and coldest
   temperatures reached, frost days), water (precipitation, relative and specific humidity, evaporation, root-zone
   and surface soil moisture, snow depth) and air & energy (wind speed, sunlight at the surface, cloud cover).
   Every variable has a plain-language definition, its data source and a note on why it matters.
   The **What is changing?** tab tests all 14 at once and ranks them by strength of evidence, so users can find
   variables that are trending instead of guessing.
2. **Choose a place (where).** Five Mongolian regions (Ulaanbaatar, South Gobi, Lake Khuvsgul, the Altai and the
   Eastern Steppe), three global contrasts (Amazon, Sahel, Arctic), any latitude/longitude on Earth (fetched live),
   or the **whole of Mongolia** as an area-weighted average of every NASA POWER grid cell inside the border.
   The **map** tab computes a trend for each of the 587 grid cells inside Mongolia and marks where the trend is
   significant. Clicking any cell shows that place's own time series and verdict, and a **Play** button animates
   Mongolia year by year (each year compared with the 1981-2010 average).
3. **See the time series (how much).** Interactive charts of yearly or seasonal values (winter, spring, summer,
   autumn) with the trend line, its 95% confidence band and Sen's slope. The rate of change is shown per decade and
   over the whole period. Data can be downloaded as CSV.
4. **Test significance.** Least-squares regression with a t-test and 95% confidence interval, the Mann-Kendall test
   (with tie correction) and Sen's slope. A trend is called significant only when both tests agree at the 5% level.
   When a trend is not significant, the app estimates how many years of data would be needed if it continued,
   following the challenge's note that some trends only need a longer record.
5. **Compare regions.** Compare mode puts two places side by side on one chart and flags when a variable trends in
   opposite directions, which the challenge highlights as a key difficulty.

**Guided missions.** Six demo missions set up the app and ask questions, for example *Summer vs winter in
Ulaanbaatar*, *Warm Arctic, cold Mongolia?*, *Is northern Mongolia drying out?* and *Are Gobi winds slowing down?*
Before the evidence appears, students make a guess ("going up", "going down" or "no real trend") and get feedback,
so they practise reading evidence instead of being told results.
Teachers can share a mission directly by adding `?mission=1` to `?mission=6` to the app link.

**What I found (NASA POWER, 1981-2025).**
- **Mongolia is warming.** The country-average air temperature rose **+0.18 °C per decade** (t-test p = 0.009,
  Mann-Kendall p = 0.005), about +0.8 °C over 44 years. **62%** of Mongolia's area shows significant warming and
  none shows significant cooling. Warming is strongest in the south-west (Altai and Gobi-Altai) and north-east, up to
  +0.40 °C per decade, and weakest in the central Gobi.
- **Seasons tell different stories.** Summer warming is significant at 3 of the 5 Mongolian sites (average
  +0.33 °C per decade; Ulaanbaatar +0.30 °C, p = 0.02). Winters lean colder at all five sites (average
  -0.17 °C per decade), but none of those trends is significant. Over the same years, winters in Svalbard (Arctic)
  warmed **+1.39 °C per decade** (p < 0.001): opposite directions, consistent with the "warm Arctic, cold
  continent" pattern some scientists describe, though this data alone cannot prove the link.
- **Winds are slowing.** Country-average wind speed fell 0.039 m/s per decade (significant), with significant
  decreases over 32% of Mongolia; in the South Gobi, -0.17 m/s per decade.
- **Fewer frost days on the Eastern Steppe:** -1.5 days per decade (p = 0.04). Using only 2000-2025 the trend is no
  longer significant, which shows students why record length matters.
- **Not everything is trending.** Country-average precipitation, root-zone soil moisture and snow depth show no
  significant trend over 1981-2025. That is an important result too.

**Why it matters for Mongolia.** Herders, farmers and cities in Mongolia feel climate change through dzud (harsh
winters that kill livestock), desertification and dust storms in the Gobi, and permafrost thaw in the north. A tool
that lets students in Ulaanbaatar test these changes themselves, with NASA data and real statistics, builds the data
skills and climate literacy the country needs.

**Scientific honesty built in.** The app never invents data: when NASA POWER cannot be reached it uses a bundled
snapshot of real NASA data, or says clearly that data is unavailable. It warns when sunlight and cloud cover cross
the 2001 change of data source, when neighbouring years are correlated, and that testing many variables means some
will look significant by chance.

**Tools used.** Python, Streamlit, Plotly, pandas, NumPy and SciPy, starting from the open-source
kdmayer/nasa-power-api downloader (MIT License). The statistics are covered by 20 unit tests (including a check of
the Mann-Kendall implementation against SciPy's Kendall tau). The app can be hosted free on Streamlit Community Cloud.

**Audience.** High school and university students and members of the public with some science background, as the
challenge suggests. All text is in plain English with definitions for every variable and statistical term.

**Next steps.** Mongolian language interface, more variables from GLDAS and MODIS (vegetation greenness, land
surface temperature), seasonal trend maps, and a trend test that corrects for autocorrelation.

## Use of Super Intelligence (SI)

Yes. I chose the challenge, the approach (a NASA POWER trend dashboard with significance testing) and the Mongolian
focus, and built a first working version of the app. I then used **Claude Code**, Anthropic's AI coding assistant, to
review that version and to write most of the new code: the Mann-Kendall test, confidence intervals and Sen's slope,
the data loading and bundled NASA snapshot, the Mongolia map and country average, seasons, compare mode and the
guided missions, the clickable map, the year-by-year animation and the guessing game. It also wrote the unit tests
and README, built the interactive web slides and the PDF slides from the app's real charts and screenshots, and
helped draft this text. I checked the app and its results and am responsible for the final project.

Where SI was used is marked in the project itself: a note at the top of each code file, a "Use of AI" section in
the README, an AI co-author line on every code commit, and a footer on the last demo slide. All data and every number
come from NASA POWER and are computed by the app's code. No SI-generated images, video, audio or data are used, and
no NASA logos or branding appear anywhere.

## NASA Data

- **NASA POWER (Prediction Of Worldwide Energy Resources), NASA Langley Research Center.** Monthly and annual point
  API and regional API, version 2, `RE` community, 1981-2025. https://power.larc.nasa.gov
  - Used for every chart, test, map and average in the app.
  - Variables (POWER codes): T2M, T2M_MAX, T2M_MIN, FROST_DAYS, PRECTOTCORR, RH2M, QV2M, EVLAND, GWETROOT, GWETTOP,
    SNODP, WS2M, ALLSKY_SFC_SW_DWN, CLOUD_AMT.
- **MERRA-2 (Modern-Era Retrospective analysis for Research and Applications, Version 2), NASA Global Modeling and
  Assimilation Office**, delivered through POWER: temperature, frost days, precipitation (corrected with gauge and
  satellite observations), humidity, evaporation, soil moisture, snow depth and wind.
- **CERES (Clouds and the Earth's Radiant Energy System) SYN1deg** (2001 onward) and **GEWEX SRB** (1984-2000),
  delivered through POWER: sunlight at the surface and cloud cover.

Data acknowledgement: "The data was obtained from the National Aeronautics and Space Administration (NASA) Langley
Research Center (LaRC) Prediction of Worldwide Energy Resource (POWER) Project funded through the NASA Earth
Science/Applied Science Program."

## Space Agency Partner Data and Other References

No Space Agency Partner data was used.

Other data, code and tools:
- Natural Earth 1:50m Admin 0 countries (public domain): Mongolia border. https://www.naturalearthdata.com
- kdmayer/nasa-power-api by Kevin Mayer (MIT License): starting code. https://github.com/kdmayer/nasa-power-api
- Streamlit, Plotly, pandas, NumPy, SciPy, Requests (open-source Python libraries).
- Claude Code (Anthropic): AI coding assistant (see Use of SI).

References:
1. NASA POWER Project, NASA Langley Research Center. https://power.larc.nasa.gov
2. Gelaro, R., et al. (2017). The Modern-Era Retrospective Analysis for Research and Applications, Version 2
   (MERRA-2). *Journal of Climate*, 30(14), 5419-5454. https://doi.org/10.1175/JCLI-D-16-0758.1
3. Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica*, 13(3), 245-259.
4. Kendall, M. G. (1975). *Rank Correlation Methods* (4th ed.). Charles Griffin, London.
5. Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *Journal of the American
   Statistical Association*, 63(324), 1379-1389.
6. IPCC (2018). *Global Warming of 1.5 °C*. Chapter 1: Framing and Context (current warming rate of about 0.2 °C
   per decade).
7. NASA Space Apps Challenge 2026, "Be An Earth System Trend Detective!" challenge statement and resources.
   https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/

## Tags (if the form asks for them)

#EarthScience #ClimateChange #TrendAnalysis #Statistics #MannKendall #DataVisualization #NASAPOWER #MERRA2 #Mongolia #Education #Streamlit
