"""Daily kitesurf forecast check for Quebec lakes.

Fetches weather from multiple sources, evaluates each hour against personal
criteria, writes data for the dashboard, and sends a Telegram alert only if
at least one spot has green conditions today or tomorrow.
"""

import json
import os
import sys
import time
import zoneinfo
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    COMPASS,
    COMPASS_TOLERANCE,
    CRITERIA,
    SPOTS,
    TIMEZONE,
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL",
    "https://julien-lavergne-roberge.github.io/kite-quebec-alerts/",
)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
MET_NORWAY_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
MET_NORWAY_UA = "KiteQuebecAlerts/1.0 github.com/kite-quebec-alerts"

TZ = zoneinfo.ZoneInfo(TIMEZONE)

HTTP_TIMEOUT = 30

def _session():
    s = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

SESSION = _session()


def fetch_open_meteo(lat, lon, model="best_match"):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m,wind_direction_10m",
        "wind_speed_unit": "kn",
        "timezone": TIMEZONE,
        "forecast_days": 2,
        "models": model,
    }
    r = SESSION.get(OPEN_METEO_URL, params=params, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_met_norway(lat, lon):
    headers = {"User-Agent": MET_NORWAY_UA}
    r = SESSION.get(
        MET_NORWAY_URL,
        params={"lat": lat, "lon": lon},
        headers=headers,
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def ms_to_knots(ms):
    return ms * 1.94384


def direction_matches(degrees, allowed_dirs):
    for d in allowed_dirs:
        center = COMPASS[d]
        diff = abs((degrees - center + 180) % 360 - 180)
        if diff <= COMPASS_TOLERANCE:
            return True
    return False


def evaluate_hour(wind, gust, temp, precip, direction, allowed_dirs):
    c = CRITERIA
    if not direction_matches(direction, allowed_dirs):
        return "red", "vent off-shore"
    if gust > c["gust_max"]:
        return "red", f"rafales {gust:.0f} kn"
    if temp < c["temp_min"]:
        return "red", f"{temp:.0f}°C"
    if precip > c["precip_max_mmh"]:
        return "red", f"pluie {precip:.1f} mm/h"
    if wind < c["wind_min"] or wind > c["wind_max"]:
        return "red", f"vent {wind:.0f} kn"
    if c["wind_ideal_min"] <= wind <= c["wind_ideal_max"] and gust < 30 and precip < 0.5:
        return "green", f"{wind:.0f}/{gust:.0f} kn"
    return "yellow", f"{wind:.0f}/{gust:.0f} kn"


def process_open_meteo(data, allowed_dirs):
    h = data["hourly"]
    out = []
    for i, t in enumerate(h["time"]):
        hour = datetime.fromisoformat(t).hour
        if not (CRITERIA["hours_min"] <= hour <= CRITERIA["hours_max"]):
            continue
        wind = h["wind_speed_10m"][i]
        gust = h["wind_gusts_10m"][i]
        temp = h["temperature_2m"][i]
        precip = h["precipitation"][i] or 0
        direction = h["wind_direction_10m"][i]
        if wind is None or direction is None:
            continue
        status, reason = evaluate_hour(wind, gust, temp, precip, direction, allowed_dirs)
        out.append({
            "time": t,
            "status": status,
            "reason": reason,
            "wind": wind,
            "gust": gust,
            "temp": temp,
            "precip": precip,
            "dir": direction,
        })
    return out


def process_met_norway(data, allowed_dirs):
    series = data["properties"]["timeseries"]
    out = []
    now_local = datetime.now(TZ)
    limit = now_local + timedelta(days=2)
    for entry in series:
        t_utc = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
        t_local = t_utc.astimezone(TZ)
        if t_local < now_local - timedelta(hours=1) or t_local > limit:
            continue
        if not (CRITERIA["hours_min"] <= t_local.hour <= CRITERIA["hours_max"]):
            continue
        inst = entry["data"]["instant"]["details"]
        wind = ms_to_knots(inst.get("wind_speed", 0))
        gust = ms_to_knots(inst.get("wind_speed_of_gust", inst.get("wind_speed", 0) * 1.3))
        temp = inst.get("air_temperature", -99)
        direction = inst.get("wind_from_direction", 0)
        next1h = entry["data"].get("next_1_hours", {}).get("details", {})
        precip = next1h.get("precipitation_amount", 0) or 0
        status, reason = evaluate_hour(wind, gust, temp, precip, direction, allowed_dirs)
        out.append({
            "time": t_local.strftime("%Y-%m-%dT%H:%M"),
            "status": status,
            "reason": reason,
            "wind": wind,
            "gust": gust,
            "temp": temp,
            "precip": precip,
            "dir": direction,
        })
    return out


def consensus_status(per_source):
    statuses = [s for s in per_source.values() if s]
    if not statuses:
        return "unknown"
    counts = Counter(statuses)
    top, count = counts.most_common(1)[0]
    if count >= 2:
        return top
    return "yellow"


def analyze_spot(spot):
    results = {"open_meteo": [], "gem": [], "met_norway": []}

    try:
        om = fetch_open_meteo(spot["lat"], spot["lon"], "best_match")
        results["open_meteo"] = process_open_meteo(om, spot["allowed_dirs"])
    except Exception as e:
        print(f"[{spot['name']}] Open-Meteo error: {e}", file=sys.stderr)

    try:
        gem = fetch_open_meteo(spot["lat"], spot["lon"], "gem_seamless")
        results["gem"] = process_open_meteo(gem, spot["allowed_dirs"])
    except Exception as e:
        print(f"[{spot['name']}] GEM (Env Canada) error: {e}", file=sys.stderr)

    try:
        met = fetch_met_norway(spot["lat"], spot["lon"])
        results["met_norway"] = process_met_norway(met, spot["allowed_dirs"])
    except Exception as e:
        print(f"[{spot['name']}] MET Norway error: {e}", file=sys.stderr)

    by_time = {}
    for h in results["open_meteo"]:
        key = h["time"][:13]
        by_time[key] = {"primary": h, "statuses": {"open_meteo": h["status"]}}
    for h in results["gem"]:
        key = h["time"][:13]
        if key in by_time:
            by_time[key]["statuses"]["gem"] = h["status"]
    for h in results["met_norway"]:
        key = h["time"][:13]
        if key in by_time:
            by_time[key]["statuses"]["met_norway"] = h["status"]

    merged = []
    for key in sorted(by_time.keys()):
        entry = by_time[key]
        p = entry["primary"]
        merged.append({
            "time": p["time"],
            "status": consensus_status(entry["statuses"]),
            "sources": entry["statuses"],
            "wind": round(p["wind"], 1),
            "gust": round(p["gust"], 1),
            "temp": round(p["temp"], 1),
            "precip": round(p["precip"], 2),
            "dir": round(p["dir"]),
            "reason": p["reason"],
        })
    return merged


def day_best(hourly, day_iso):
    day_hours = [h for h in hourly if h["time"].startswith(day_iso)]
    if not day_hours:
        return None
    rank = {"green": 0, "yellow": 1, "red": 2, "unknown": 3}
    best = min(day_hours, key=lambda h: rank.get(h["status"], 9))
    return best["status"]


def build_summary():
    today = datetime.now(TZ).date()
    tomorrow = today + timedelta(days=1)
    spots_data = []
    for spot in SPOTS:
        print(f"Checking {spot['name']}...", flush=True)
        hourly = analyze_spot(spot)
        time.sleep(0.5)
        spots_data.append({
            "name": spot["name"],
            "allowed_dirs": spot["allowed_dirs"],
            "today": day_best(hourly, today.isoformat()),
            "tomorrow": day_best(hourly, tomorrow.isoformat()),
            "hourly": hourly,
        })
    return {
        "generated_at": datetime.now(TZ).isoformat(),
        "today": today.isoformat(),
        "tomorrow": tomorrow.isoformat(),
        "spots": spots_data,
    }


def format_telegram_message(summary):
    green_today_or_tomorrow = any(
        s["today"] == "green" or s["tomorrow"] == "green" for s in summary["spots"]
    )
    if not green_today_or_tomorrow:
        return None

    emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⚪"}
    lines = ["🪁 *Alerte kite Québec*", ""]
    for s in summary["spots"]:
        today_e = emoji.get(s["today"], "⚪")
        tom_e = emoji.get(s["tomorrow"], "⚪")
        lines.append(f"{today_e}→{tom_e} *{s['name']}*")
        for day_key, day_label in [("today", "Auj"), ("tomorrow", "Demain")]:
            if s[day_key] == "green":
                day_iso = summary[day_key]
                greens = [h for h in s["hourly"] if h["time"].startswith(day_iso) and h["status"] == "green"]
                if greens:
                    times = ", ".join(f"{h['time'][11:16]} ({h['wind']:.0f}kn)" for h in greens)
                    lines.append(f"  {day_label}: {times}")
    lines.append("")
    lines.append(f"Dashboard: {DASHBOARD_URL}")
    return "\n".join(lines)


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram creds missing — printing message instead:\n")
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    r.raise_for_status()
    print("Telegram sent.")


def main():
    summary = build_summary()
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    (docs / "data.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    msg = format_telegram_message(summary)
    if msg:
        send_telegram(msg)
    else:
        print("No green spots today or tomorrow — no alert sent.")


if __name__ == "__main__":
    main()
