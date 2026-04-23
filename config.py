"""Kitesurf spots and personal criteria for Quebec alerts."""

COMPASS = {
    "N": 0, "NE": 45, "E": 90, "SE": 135,
    "S": 180, "SO": 225, "O": 270, "NO": 315,
}
COMPASS_TOLERANCE = 22.5

SPOTS = [
    {
        "name": "Oka",
        "lat": 45.4667, "lon": -74.0833,
        "allowed_dirs": ["O", "SO", "S", "NO"],
    },
    {
        "name": "Saint-Placide",
        "lat": 45.5333, "lon": -74.1833,
        "allowed_dirs": ["SO", "S", "SE", "O"],
    },
    {
        "name": "Pointe-du-Moulin",
        "lat": 45.3833, "lon": -73.9333,
        "allowed_dirs": ["SO", "O", "S", "NO"],
    },
    {
        "name": "Saint-Zotique",
        "lat": 45.2500, "lon": -74.2500,
        "allowed_dirs": ["SO", "S", "SE", "O"],
    },
    {
        "name": "Salaberry-Valleyfield",
        "lat": 45.2500, "lon": -74.1300,
        "allowed_dirs": ["O", "NO", "N", "SO"],
    },
    {
        "name": "Cap-Saint-Jacques",
        "lat": 45.5167, "lon": -73.9500,
        "allowed_dirs": ["O", "NO", "N", "SO"],
    },
]

CRITERIA = {
    "wind_min": 12,
    "wind_ideal_min": 15,
    "wind_ideal_max": 25,
    "wind_max": 30,
    "gust_max": 35,
    "temp_min": 18,
    "precip_max_mmh": 2.0,
    "hours_min": 9,
    "hours_max": 19,
}

TIMEZONE = "America/Montreal"
