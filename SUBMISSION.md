# Space Apps 2026 submission text (Team Florensiza)

The sections below match the boxes on the Space Apps project page, in the same order
(from the official Project Submission Guide). All numbers come from the app (NASA POWER, 1981-2025).
When the Streamlit app is deployed, add a "Live app: <link>" line under Link to Final Project.

---

## Project Name

Earth System Trend Detective

## High-Level Project Summary

Is Mongolia's climate really changing? Most people guess. Earth System Trend Detective lets anyone check. It is a
free web tool that turns 45 years of NASA data (the MERRA-2 model and CERES satellites, through NASA POWER) into
answers to the challenge's four questions: what is changing, where, by how much, and is it significant? Pick one of
14 variables and a place, from a single point on Earth to the whole of Mongolia, and the app charts the trend, runs
two significance tests (a t-test with a 95% confidence interval, and the Mann-Kendall test) and explains the verdict
in plain words. A scanner finds which variables are moving, a clickable map shows where, and guided missions make
students guess before they see the evidence. What makes it matter is honesty: it doesn't just draw a trend line, it
tells you whether to believe it. Mongolia, for example, has warmed 0.18 °C per decade since 1981, significantly
across more than half the country, but its summers are warming while its winters are not.

## Link to Project Demo

https://bishreldev.github.io/earth-system-trend-detective/slides/

(Interactive 7-slide web presentation with live charts, publicly viewable without login. Use the arrow keys or the
buttons to move. A PDF version is linked at the top of the page and is also at
https://github.com/bishreldev/earth-system-trend-detective/blob/main/demo/Earth_System_Trend_Detective_slides.pdf)

## Link to Final Project

https://bishreldev.github.io/earth-system-trend-detective/

(Project website with a live mini version of the app at the top (choose a place, variable and season and get the
same numbers and verdict as the app), interactive charts from the app's NASA data, who it is for, how it works,
findings and six guided missions you can try in the live demo. It links to the 7-slide demo and the code.)

Code: https://github.com/bishreldev/earth-system-trend-detective

## Detailed Project Description

### Earth System Trend Detective: is Mongolia's climate really changing, or does it just feel that way?

In Mongolia, everyone has a climate story: the winter that took the herd, the summer the river ran low, the spring
dust storm that reached the capital. Stories matter, but they can't tell a real trend from one bad year. NASA has
measured and modeled Earth's climate for decades. The hard part is knowing which variables to look at, and whether
a change is real or just noise. Earth System Trend Detective turns that data into evidence anyone can check.

### What is it?

A free tool that runs in any browser, with no installation or login, built for high-school and university students
and curious citizens. You play the detective: pick a suspect (a variable), a scene (a place) and a time (a season
and a range of years), and the app tells you whether the evidence holds up.

### Features

**Find what is changing.** 14 NASA variables in three themes: temperature (air temperature, hottest and coldest
temperatures, frost days); water (precipitation, humidity, evaporation, soil moisture, snow depth); and air & energy
(wind, sunlight, cloud cover). Each one has a plain-language definition and a note on why it matters. The scanner
tests all 14 at once and ranks them, so you find trends instead of guessing where to look.

**See where it is changing.** A map of the 587 NASA grid cells inside Mongolia, each with its own trend and
significance. Click any cell to see its story year by year, or press Play and watch 45 years go by. You can also
pick any point on Earth, five Mongolian regions, three global contrasts (Amazon, Sahel, Svalbard) or the whole
country, and put two places side by side to spot opposite trends.

**Measure how much.** Yearly or seasonal charts with the trend line and its 95% confidence band. The change is given
per decade and over the whole record, and every series can be downloaded as CSV.

**Prove it's real.** A least-squares trend with a t-test and 95% confidence interval, the Mann-Kendall test and
Sen's slope. A trend counts as significant only when both tests agree. If it isn't significant yet, the app
estimates how many more years of data it would need.

**Learn by guessing first.** Six guided missions, such as *Summer vs winter in Ulaanbaatar* and *Svalbard vs
Ulaanbaatar winters: test a debated idea*, ask a question and make students predict "going up", "going down" or "no
real trend" before the evidence appears. They run in the live demo on the project website, and each one has a link
a teacher can share.

### The difference: a detective that admits what it doesn't know

Plenty of tools draw a line through data. Few tell you when not to believe it. Trend Detective is built to catch
false clues:
- Sunlight and cloud data change source in 2001, so the app tests them on 2001-2025 only. When we did this, an
  apparent sunlight trend in the Gobi disappeared.
- Testing 587 map cells at once lets about 5% look significant by chance, so the app also reports the area that
  survives a Benjamini-Hochberg correction: warming covers 62% of Mongolia before correction and 55% after.
- When the two tests disagree, the app says so and shows both p-values instead of hiding the conflict.
- It never invents data. A bundled snapshot of real NASA data keeps it working on slow Wi-Fi.

### What I found (NASA POWER, 1981-2025)

- **Mongolia is warming.** The country average rose **+0.18 °C per decade** (t-test p = 0.009, Mann-Kendall
  p = 0.005), about +0.8 °C in 44 years. 62% of the country warmed significantly (55% after correction) and none
  cooled. Warming is strongest in the south-west, up to +0.40 °C per decade, and close to zero in the central Gobi.
- **Seasons tell different stories.** Summers warmed significantly at 3 of 5 Mongolian sites (average +0.33 °C per
  decade; Ulaanbaatar +0.30 °C, p = 0.02). Winters lean colder at all five (average -0.17 °C per decade), but none
  significantly. Meanwhile Svalbard winters (one Arctic grid point) warmed **+1.39 °C per decade** (p < 0.001). The
  suggested link between the two ("warm Arctic, cold continent") is still debated, so the app treats it as an idea
  to test, not a result.
- **Winds are slowing on average, but not everywhere.** Country-average wind fell 0.039 m/s per decade
  (significant), and the South Gobi 0.17 m/s per decade, while Lake Khuvsgul's wind rose significantly.
- **Record length matters.** Frost days on the Eastern Steppe fell 1.5 per decade (t-test p = 0.04, Mann-Kendall
  p = 0.045), but using only 2000-2025 the trend is no longer significant.
- **Not everything is trending.** Country-average precipitation, root-zone soil moisture and snow depth show no
  significant trend. That is a result too.

### Why it matters for Mongolia

Herders, farmers and cities in Mongolia feel climate change through dzud (harsh winters that kill livestock),
desertification and dust storms in the Gobi, and permafrost thaw in the north. A tool that lets students in
Ulaanbaatar test these changes themselves, with NASA data and real statistics, builds the data skills and climate
literacy the country needs.

### How it's built

Python, Streamlit, Plotly, pandas, NumPy and SciPy, starting from the open-source kdmayer/nasa-power-api downloader
(MIT License). 24 unit tests check the statistics, including the Mann-Kendall test against SciPy's Kendall tau. The
project website runs a mini version of the app in the browser using the app's own results, so its numbers match
the app exactly.

### What's next

A Mongolian-language version for schools and herder communities, more NASA data (GLDAS soil water and streamflow,
MODIS vegetation greenness), seasonal trend maps, and trend tests that correct for year-to-year memory.

Because before we can adapt to a changing climate, we need to know what has really changed.

## Use of Super Intelligence (SI)

Yes. I chose the challenge, the approach (a NASA POWER trend dashboard with significance testing) and the Mongolian
focus, and built a first working version of the app. I then used **Claude Code**, Anthropic's AI coding assistant, to
review that version and to write most of the new code: the Mann-Kendall test, confidence intervals and Sen's slope,
the data loading and bundled NASA snapshot, the Mongolia map and country average, seasons, compare mode and the
guided missions, the clickable map, the year-by-year animation and the guessing game. It also wrote the unit tests
and README, built the project website, the interactive web slides and the PDF slides from the app's real charts and
screenshots, and helped draft this text. I checked the app and its results and am responsible for the final project.

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
