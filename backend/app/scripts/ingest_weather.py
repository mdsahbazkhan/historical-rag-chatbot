"""
Fetch 5 years (2021-01-01 → 2025-12-31) of REAL daily weather data for 10
major Indian cities from the Open-Meteo Archive API and store in MongoDB.

API:  https://open-meteo.com/en/docs/historical-weather-api
Cost: Completely FREE — no API key required.
Rate: ~1 req / city; a 1-second sleep between cities is enough.

Run from backend/:
    python -m app.scripts.ingest_weather
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import time
import requests
from app.config.database import db

weather_collection = db["weather_data"]

# Open-Meteo historical archive endpoint
_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Ten major Indian cities with their GPS coordinates
CITIES: dict[str, dict] = {
    "Delhi":       {"lat": 28.6139,  "lon": 77.2090},
    "Mumbai":      {"lat": 19.0760,  "lon": 72.8777},
    "Chennai":     {"lat": 13.0827,  "lon": 80.2707},
    "Hyderabad":   {"lat": 17.3850,  "lon": 78.4867},
    "Bangalore":   {"lat": 12.9716,  "lon": 77.5946},
    "Kolkata":     {"lat": 22.5726,  "lon": 88.3639},
    "Pune":        {"lat": 18.5204,  "lon": 73.8567},
    "Ahmedabad":   {"lat": 23.0225,  "lon": 72.5714},
    "Jaipur":      {"lat": 26.9124,  "lon": 75.7873},
    "Lucknow":     {"lat": 26.8467,  "lon": 80.9462},
}

# Daily variables requested from the API
_DAILY_VARS = ",".join([
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "windspeed_10m_max",
    "relative_humidity_2m_max",
    "weathercode",
])

# WMO weather interpretation codes → human-readable condition string
_WMO_CONDITIONS: dict[int, str] = {
    0:  "Clear Sky",
    1:  "Mostly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy",        48: "Icy Fog",
    51: "Light Drizzle",53: "Drizzle",      55: "Heavy Drizzle",
    61: "Light Rain",   63: "Rainy",        65: "Heavy Rain",
    71: "Light Snow",   73: "Snow",         75: "Heavy Snow",
    77: "Snow Grains",
    80: "Light Showers",81: "Showers",      82: "Violent Showers",
    85: "Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm with Hail",
    99: "Thunderstorm with Heavy Hail",
}


def _fetch_city(city: str, lat: float, lon: float, start: str, end: str) -> list[dict]:
    """Call Open-Meteo for one city and return a list of daily records."""
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "start_date": start,
        "end_date":   end,
        "daily":      _DAILY_VARS,
        "timezone":   "Asia/Kolkata",
    }
    resp = requests.get(_BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    daily  = data.get("daily", {})
    dates  = daily.get("time", [])
    t_mean = daily.get("temperature_2m_mean", [])
    t_max  = daily.get("temperature_2m_max", [])
    t_min  = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    wind   = daily.get("windspeed_10m_max", [])
    humid  = daily.get("relative_humidity_2m_max", [])
    wcodes = daily.get("weathercode", [])

    records: list[dict] = []
    for i, date_str in enumerate(dates):
        mean_temp = t_mean[i] if i < len(t_mean) else None
        if mean_temp is None:
            continue   # Skip days with no data

        wcode     = int(wcodes[i]) if (i < len(wcodes) and wcodes[i] is not None) else 0
        condition = _WMO_CONDITIONS.get(wcode, "Unknown")

        records.append({
            "city":            city,
            "date":            date_str,
            "temperature":     round(float(mean_temp), 1),
            "temperature_max": round(float(t_max[i]),  1) if (i < len(t_max)  and t_max[i]  is not None) else None,
            "temperature_min": round(float(t_min[i]),  1) if (i < len(t_min)  and t_min[i]  is not None) else None,
            "humidity":        round(float(humid[i]),  1) if (i < len(humid)  and humid[i]  is not None) else None,
            "wind_speed":      round(float(wind[i]),   1) if (i < len(wind)   and wind[i]   is not None) else None,
            "rainfall_mm":     round(float(precip[i]), 1) if (i < len(precip) and precip[i] is not None) else 0.0,
            "condition":       condition,
            "weather_code":    wcode,
        })

    return records


def main() -> None:
    print("Dropping existing weather_data collection …")
    weather_collection.drop()

    print("Creating compound index on (city, date) …")
    weather_collection.create_index([("city", 1), ("date", 1)], unique=True)

    start_date = "2021-01-01"
    end_date   = "2025-12-31"
    grand_total = 0

    for city, coords in CITIES.items():
        print(f"  Fetching {city} from Open-Meteo …", end=" ", flush=True)
        try:
            records = _fetch_city(city, coords["lat"], coords["lon"], start_date, end_date)
            if records:
                weather_collection.insert_many(records, ordered=False)
                grand_total += len(records)
                print(f"{len(records):,} records inserted.")
            else:
                print("no data returned.")
        except requests.HTTPError as exc:
            print(f"HTTP error — {exc}")
        except Exception as exc:
            print(f"ERROR — {exc}")

        time.sleep(1)  # Be polite to the free API

    print(f"\nWeather ingestion complete — {grand_total:,} real records in MongoDB.")


if __name__ == "__main__":
    main()
