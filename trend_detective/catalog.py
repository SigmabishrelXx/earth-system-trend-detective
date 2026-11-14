"""Locations, variables, seasons and demo missions used across the app.

Everything a student sees about a variable (name, unit, plain-language definition,
data source and why it matters) lives here so the app and the docs stay consistent.

AI disclosure: written with help from Claude Code (Anthropic's AI coding assistant). See README, "Use of AI".
"""

from __future__ import annotations

START_YEAR = 1981  # first year of NASA POWER MERRA-2 meteorology
END_YEAR = 2025  # last complete year available from POWER (checked 2026-11-14)
COMMUNITY = "RE"  # POWER "Renewable Energy" community -> solar in kWh/m^2/day

MERRA2 = "MERRA-2 (NASA GMAO global reanalysis model)"
MERRA2_PRECIP = "MERRA-2, corrected with rain-gauge and satellite observations"
CERES = "CERES SYN1deg satellite data (2001+) and GEWEX SRB (1984-2000)"
SHORT_SOURCE = {MERRA2: "MERRA-2 model", MERRA2_PRECIP: "MERRA-2 + gauges", CERES: "CERES / SRB satellite"}
# Variables whose source changes in 2001 (GEWEX SRB -> CERES); a step there can look like a trend.
SOURCE_SWITCH_YEAR = 2001

# key -> metadata. `agg` is how monthly values combine into a season.
# `raw_unit` is what the POWER API returns for the RE community (verified in tests).
VARIABLES: dict[str, dict] = {
    "T2M": {
        "label": "Air temperature",
        "unit": "°C",
        "raw_unit": "C",
        "theme": "Temperature",
        "agg": "mean",
        "palette": "warm",
        "definition": "Air temperature about 2 m above the ground, where people and animals feel it, averaged over the period.",
        "why": "Warming thaws permafrost, shifts growing seasons and stresses pasture, livestock and water supplies.",
        "source": MERRA2,
    },
    "T2M_MAX": {
        "label": "Highest temperature reached",
        "unit": "°C",
        "raw_unit": "C",
        "theme": "Temperature",
        "agg": "max",
        "palette": "warm",
        "definition": "The warmest hourly air temperature (2 m) reached during the period. A measure of heat extremes.",
        "why": "Hotter extremes raise drought and wildfire risk and put heat stress on people and herds.",
        "source": MERRA2,
    },
    "T2M_MIN": {
        "label": "Lowest temperature reached",
        "unit": "°C",
        "raw_unit": "C",
        "theme": "Temperature",
        "agg": "min",
        "palette": "warm",
        "definition": "The coldest hourly air temperature (2 m) reached during the period. A measure of cold extremes.",
        "why": "Extreme cold drives dzud livestock losses in Mongolia; milder cold extremes signal a shrinking frozen season.",
        "source": MERRA2,
    },
    "FROST_DAYS": {
        "label": "Frost days",
        "unit": "days",
        "raw_unit": "Days",
        "theme": "Temperature",
        "agg": "sum",
        "palette": "cold",
        "definition": "Number of days when the air temperature dropped below 0 °C.",
        "why": "Fewer frost days mean a longer growing season, but also thawing ground and new pests.",
        "source": MERRA2,
    },
    "PRECTOTCORR": {
        "label": "Precipitation",
        "unit": "mm/day",
        "raw_unit": "mm/day",
        "theme": "Water",
        "agg": "mean",
        "palette": "wet",
        "definition": "Average rain plus melted snow falling per day.",
        "why": "Rain and snow feed pastures, rivers and lakes. Long dry spells drive drought and desertification.",
        "source": MERRA2_PRECIP,
    },
    "RH2M": {
        "label": "Relative humidity",
        "unit": "%",
        "raw_unit": "%",
        "theme": "Water",
        "agg": "mean",
        "palette": "wet",
        "definition": "How close the air is to being saturated with water vapour (100% means it cannot hold any more).",
        "why": "Drier air pulls more water out of soil and plants, which makes droughts worse.",
        "source": MERRA2,
    },
    "QV2M": {
        "label": "Specific humidity",
        "unit": "g/kg",
        "raw_unit": "g/kg",
        "theme": "Water",
        "agg": "mean",
        "palette": "wet",
        "definition": "The actual amount of water vapour in the air: grams of water per kilogram of air.",
        "why": "Warmer air can hold about 7% more water vapour per °C, which can fuel heavier rain events.",
        "source": MERRA2,
    },
    "EVLAND": {
        "label": "Evaporation from land",
        "unit": "mm/day",
        "raw_unit": "mm/day",
        "theme": "Water",
        "agg": "mean",
        "palette": "wet",
        "definition": "Water evaporating from soil and plants back into the air, per day.",
        "why": "Evaporation links the soil to the atmosphere. It changes with temperature, soil water and vegetation.",
        "source": MERRA2,
    },
    "GWETROOT": {
        "label": "Root-zone soil moisture",
        "unit": "0-1",
        "raw_unit": "1",
        "theme": "Water",
        "agg": "mean",
        "palette": "wet",
        "definition": "How wet the soil is down to about 1 m deep, where roots grow. 0 is completely dry, 1 is fully saturated.",
        "why": "Root-zone moisture decides whether grass grows. It is a key signal for herders and for desertification.",
        "source": MERRA2,
    },
    "GWETTOP": {
        "label": "Surface soil moisture",
        "unit": "0-1",
        "raw_unit": "1",
        "theme": "Water",
        "agg": "mean",
        "palette": "wet",
        "definition": "How wet the top few centimetres of soil are, from 0 (dry) to 1 (saturated).",
        "why": "Surface soil dries first in a drought, and dry loose soil feeds dust storms.",
        "source": MERRA2,
    },
    "SNODP": {
        "label": "Snow depth",
        "unit": "cm",
        "raw_unit": "cm",
        "theme": "Water",
        "agg": "mean",
        "palette": "cold",
        "definition": "Average depth of snow lying on the ground.",
        "why": "Snow insulates the soil and stores water for spring. Very deep snow buries pasture and can cause a 'white dzud'.",
        "source": MERRA2,
    },
    "WS2M": {
        "label": "Wind speed",
        "unit": "m/s",
        "raw_unit": "m/s",
        "theme": "Air & energy",
        "agg": "mean",
        "palette": "neutral",
        "definition": "Average wind speed 2 m above the ground.",
        "why": "Wind lifts dust in the Gobi and moves heat and moisture. Many land regions show slowing winds ('stilling').",
        "source": MERRA2,
    },
    "ALLSKY_SFC_SW_DWN": {
        "label": "Sunlight at the surface",
        "unit": "kWh/m²/day",
        "raw_unit": "kW-hr/m^2/day",
        "theme": "Air & energy",
        "agg": "mean",
        "palette": "neutral",
        "definition": "Solar energy reaching the ground each day, after clouds, dust and haze have blocked some of it.",
        "why": "Changes reveal shifts in cloud cover and air pollution, and matter for solar power and plant growth.",
        "source": CERES,
    },
    "CLOUD_AMT": {
        "label": "Cloud cover",
        "unit": "%",
        "raw_unit": "%",
        "theme": "Air & energy",
        "agg": "mean",
        "palette": "neutral",
        "definition": "Percentage of the sky covered by cloud.",
        "why": "Clouds control how much sunlight reaches the ground and how much heat escapes at night.",
        "source": CERES,
    },
}

# Variables included in the bundled Mongolia grid (map + country average).
MAP_VARIABLES = [
    "T2M",
    "T2M_MIN",
    "FROST_DAYS",
    "PRECTOTCORR",
    "RH2M",
    "GWETROOT",
    "SNODP",
    "EVLAND",
    "WS2M",
    "ALLSKY_SFC_SW_DWN",
]

# Bounding boxes that tile Mongolia for the POWER regional API
# (each side must be between 2 and 10 degrees; overlapping points are de-duplicated).
MONGOLIA_BOXES = [
    # (lat_min, lat_max, lon_min, lon_max)
    (41.5, 51.5, 87.5, 97.5),
    (41.5, 51.5, 97.5, 107.5),
    (41.5, 51.5, 107.5, 117.5),
    (41.5, 51.5, 117.5, 120.0),
    (50.5, 52.5, 87.5, 97.5),
    (50.5, 52.5, 97.5, 107.5),
    (50.5, 52.5, 107.5, 117.5),
    (50.5, 52.5, 117.5, 120.0),
]

MONGOLIA_REGION = "All of Mongolia (country average)"
CUSTOM = "Custom location (enter coordinates)"

# name -> (lat, lon, short description). Mongolia first, then global contrasts.
LOCATIONS: dict[str, tuple[float, float, str]] = {
    "Ulaanbaatar (capital)": (47.9184, 106.9177, "Mongolia's capital, on the forest-steppe edge at about 1,350 m."),
    "South Gobi (Dalanzadgad)": (43.5708, 104.4250, "Gobi desert-steppe, where drought and dust storms matter most."),
    "Lake Khuvsgul (northern taiga)": (51.0931, 100.4633, "Mountain taiga and permafrost near the Russian border."),
    "Altai Mountains (Khovd)": (48.0056, 91.6419, "Arid high mountains and glaciers in far-western Mongolia."),
    "Eastern Steppe (Choibalsan)": (48.0717, 114.5328, "One of the largest intact grasslands left on Earth."),
    "Amazon Rainforest (Brazil)": (-3.4653, -62.2159, "Tropical rainforest, for a humid contrast."),
    "Sahel (Niamey, Niger)": (13.5116, 2.1254, "Semi-arid belt south of the Sahara, a well-studied drought region."),
    "Arctic (Svalbard, Norway)": (78.2232, 15.6267, "High Arctic archipelago, one of the fastest-warming places on Earth."),
}
MONGOLIA_SITES = [k for k in LOCATIONS if LOCATIONS[k][0] > 40 and 87 < LOCATIONS[k][1] < 120]

SEASONS: dict[str, list[int] | None] = {
    "Whole year": None,
    "Winter (Dec-Feb)": [12, 1, 2],
    "Spring (Mar-May)": [3, 4, 5],
    "Summer (Jun-Aug)": [6, 7, 8],
    "Autumn (Sep-Nov)": [9, 10, 11],
}


def slugify(name: str) -> str:
    keep = "".join(c.lower() if c.isalnum() else "-" for c in name)
    return "-".join(p for p in keep.split("-") if p)


def var_title(key: str) -> str:
    v = VARIABLES[key]
    return f"{v['label']} ({v['unit']})"
