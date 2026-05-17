"""Daily kitesurf forecast for Quebec lakes — per-source, any-source alerting.

Fetches weather from 3 sources, keeps RAW per-source hourly data (no consensus),
detects per-source alert windows, and notifies if ANY source shows ≥12 kn for
≥3 consecutive hours with an acceptable wind direction. The user judges
goodness from the dashboard.

Appends a compact snapshot to docs/history.jsonl on every run.
"""

import json
import os
import smtplib
import sys
import time
import zoneinfo
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    ALERT_CRITERIA,
    COMPASS,
    COMPASS_TOLERANCE,
    CRITERIA,
    SPOTS,
    TIMEZONE,
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
FRIEND_EMAIL = os.environ.get("FRIEND_EMAIL")
CC_EMAIL = os.environ.get("CC_EMAIL")
DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL",
    "https://julien-lavergne-roberge.github.io/kite-quebec-alerts/",
)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
MET_NORWAY_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
MET_NORWAY_UA = "KiteQuebecAlerts/1.0 github.com/kite-quebec-alerts"

TZ = zoneinfo.ZoneInfo(TIMEZONE)
HTTP_TIMEOUT = 30
SOURCES = ["open_meteo", "gem", "met_norway"]


def _session():
    s = requests.Session()
    retry = Retry(
        total=2, backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


SESSION = _session()


def fetch_open_meteo(lat, lon, model="best_match"):
    params = {
        "latitude": lat, "longitude": lon,
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
    r = SESSION.get(
        MET_NORWAY_URL,
        params={"lat": lat, "lon": lon},
        headers={"User-Agent": MET_NORWAY_UA},
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


def deg_to_cardinal(deg):
    return ["N", "NE", "E", "SE", "S", "SO", "O", "NO"][round(deg / 45) % 8]


def process_open_meteo_raw(data, allowed_dirs):
    """Return clean hourly list with raw values (no status)."""
    h = data["hourly"]
    out = []
    for i, t in enumerate(h["time"]):
        hour = datetime.fromisoformat(t).hour
        if not (CRITERIA["hours_min"] <= hour <= CRITERIA["hours_max"]):
            continue
        wind = h["wind_speed_10m"][i]
        direction = h["wind_direction_10m"][i]
        if wind is None or direction is None:
            continue
        out.append({
            "time": t,
            "wind": round(wind, 1),
            "gust": round(h["wind_gusts_10m"][i] or 0, 1),
            "temp": round(h["temperature_2m"][i] or -99, 1),
            "precip": round(h["precipitation"][i] or 0, 2),
            "dir": round(direction),
            "dir_ok": direction_matches(direction, allowed_dirs),
        })
    return out


def process_met_norway_raw(data, allowed_dirs):
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
        out.append({
            "time": t_local.strftime("%Y-%m-%dT%H:%M"),
            "wind": round(wind, 1),
            "gust": round(gust, 1),
            "temp": round(temp, 1),
            "precip": round(precip, 2),
            "dir": round(direction),
            "dir_ok": direction_matches(direction, allowed_dirs),
        })
    return out


def find_alert_window(hourly, day_iso):
    """Longest consecutive run on day_iso where wind ≥ wind_min AND dir_ok."""
    ac = ALERT_CRITERIA
    day_hours = sorted(
        (h for h in hourly if h["time"].startswith(day_iso)),
        key=lambda h: h["time"],
    )

    def hour_ok(h):
        return h["wind"] >= ac["wind_min"] and h["dir_ok"]

    best, current = [], []
    for h in day_hours:
        if hour_ok(h):
            current.append(h)
            if len(current) > len(best):
                best = current[:]
        else:
            current = []

    if len(best) < ac["min_consecutive_hours"]:
        return None

    winds = [h["wind"] for h in best]
    dirs = [h["dir"] for h in best]
    return {
        "start": best[0]["time"][11:16],
        "end": best[-1]["time"][11:16],
        "hours": len(best),
        "wind_min": round(min(winds)),
        "wind_max": round(max(winds)),
        "dominant_dir": deg_to_cardinal(sum(dirs) / len(dirs)),
    }


def analyze_spot(spot):
    """Return raw per-source hourly data."""
    raw = {s: [] for s in SOURCES}
    try:
        raw["open_meteo"] = process_open_meteo_raw(
            fetch_open_meteo(spot["lat"], spot["lon"], "best_match"),
            spot["allowed_dirs"],
        )
    except Exception as e:
        print(f"[{spot['name']}] Open-Meteo error: {e}", file=sys.stderr)
    try:
        raw["gem"] = process_open_meteo_raw(
            fetch_open_meteo(spot["lat"], spot["lon"], "gem_seamless"),
            spot["allowed_dirs"],
        )
    except Exception as e:
        print(f"[{spot['name']}] GEM error: {e}", file=sys.stderr)
    try:
        raw["met_norway"] = process_met_norway_raw(
            fetch_met_norway(spot["lat"], spot["lon"]),
            spot["allowed_dirs"],
        )
    except Exception as e:
        print(f"[{spot['name']}] MET Norway error: {e}", file=sys.stderr)
    return raw


def build_summary():
    today = datetime.now(TZ).date()
    tomorrow = today + timedelta(days=1)
    spots_data = []
    for spot in SPOTS:
        print(f"Checking {spot['name']}...", flush=True)
        raw = analyze_spot(spot)
        time.sleep(0.5)

        alerts = {"today": {}, "tomorrow": {}}
        for src in SOURCES:
            alerts["today"][src] = find_alert_window(raw[src], today.isoformat())
            alerts["tomorrow"][src] = find_alert_window(raw[src], tomorrow.isoformat())

        spots_data.append({
            "name": spot["name"],
            "lat": spot["lat"],
            "lon": spot["lon"],
            "allowed_dirs": spot["allowed_dirs"],
            "alerts": alerts,
            "by_source": raw,
        })
    return {
        "generated_at": datetime.now(TZ).isoformat(),
        "today": today.isoformat(),
        "tomorrow": tomorrow.isoformat(),
        "sources": SOURCES,
        "spots": spots_data,
    }


def any_alert(spot, day_key):
    return any(w is not None for w in spot["alerts"][day_key].values())


def format_telegram_message(summary):
    """Fire if any source shows an alert window for any spot today or tomorrow."""
    triggered = [
        s for s in summary["spots"]
        if any_alert(s, "today") or any_alert(s, "tomorrow")
    ]
    if not triggered:
        return None

    lines = ["🪁 *Alerte vent Québec*", ""]
    for s in triggered:
        lines.append(f"*{s['name']}*")
        for day_key, label in [("today", "Auj"), ("tomorrow", "Demain")]:
            hits = {src: w for src, w in s["alerts"][day_key].items() if w}
            if hits:
                lines.append(f"  _{label}:_")
                for src, w in hits.items():
                    lines.append(
                        f"   • {src}: {w['start']}-{w['end']} "
                        f"({w['wind_min']}-{w['wind_max']} kn, {w['dominant_dir']})"
                    )
        lines.append("")
    lines.append("Pas un consensus — vérifie le détail sur le dashboard :")
    lines.append(DASHBOARD_URL)
    return "\n".join(lines)


def format_friend_email(summary):
    """Send if any source shows alert today or tomorrow (synced with Telegram)."""
    triggered = [
        s for s in summary["spots"]
        if any_alert(s, "today") or any_alert(s, "tomorrow")
    ]
    if not triggered:
        return None

    days_hit = []
    if any(any_alert(s, "today") for s in triggered):
        days_hit.append("aujourd'hui")
    if any(any_alert(s, "tomorrow") for s in triggered):
        days_hit.append("demain")
    day_phrase = " et ".join(days_hit)

    subject = f"🪁 Vent prévu {day_phrase} ({len(triggered)} spot{'s' if len(triggered) > 1 else ''})"
    lines = [
        "Salut!",
        "",
        f"Au moins une source météo prévoit du vent (≥12 kn pendant 3h+ dans une "
        f"direction kiteable) pour {day_phrase}.",
        "",
        "Détail par spot :",
    ]
    for s in triggered:
        lines.append("")
        lines.append(f"  {s['name']}:")
        for day_key, day_label, day_iso in [
            ("today", "Aujourd'hui", summary["today"]),
            ("tomorrow", "Demain", summary["tomorrow"]),
        ]:
            day_lines = []
            for src, w in s["alerts"][day_key].items():
                if w:
                    day_lines.append(
                        f"      • selon {src}: {w['start']}-{w['end']} "
                        f"({w['wind_min']}-{w['wind_max']} kn, {w['dominant_dir']})"
                    )
            if day_lines:
                lines.append(f"    {day_label} ({day_iso}):")
                lines.extend(day_lines)
    lines += [
        "",
        "Les sources peuvent diverger. Va voir le dashboard pour comparer et décider :",
        f"  {DASHBOARD_URL}",
        "",
        "— Julien LR (alerte auto)",
    ]
    return subject, "\n".join(lines)


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram creds missing — printing message instead:\n")
        print(message)
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID, "text": message,
            "parse_mode": "Markdown", "disable_web_page_preview": True,
        },
        timeout=20,
    )
    r.raise_for_status()
    print("Telegram sent.")
    return True


def _parse_addr_list(raw):
    if not raw:
        return []
    return [a.strip() for a in raw.split(",") if a.strip()]


def send_email(subject, body):
    to_list = _parse_addr_list(FRIEND_EMAIL)
    cc_list = _parse_addr_list(CC_EMAIL)
    if not (GMAIL_USER and GMAIL_APP_PASSWORD and to_list):
        print("Gmail/friend creds missing — printing email instead:\n")
        print(f"Subject: {subject}\n\n{body}")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    recipients = to_list + cc_list
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, recipients, msg.as_string())
    print(f"Email sent to {to_list}" + (f" (CC {cc_list})" if cc_list else ""))
    return True


def append_history(summary, telegram_sent, email_sent):
    """One JSONL line per run, slim: alerts only, no raw hourly."""
    path = Path("docs/history.jsonl")
    path.parent.mkdir(exist_ok=True)
    entry = {
        "generated_at": summary["generated_at"],
        "today": summary["today"],
        "tomorrow": summary["tomorrow"],
        "telegram_sent": telegram_sent,
        "email_sent": email_sent,
        "spots": [
            {"name": s["name"], "alerts": s["alerts"]}
            for s in summary["spots"]
        ],
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    summary = build_summary()
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    (docs / "data.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    telegram_sent = False
    msg = format_telegram_message(summary)
    if msg:
        try:
            telegram_sent = send_telegram(msg)
        except Exception as e:
            print(f"Telegram failed: {e}", file=sys.stderr)
    else:
        print("No alert today or tomorrow — no Telegram sent.")

    email_sent = False
    email = format_friend_email(summary)
    if email:
        try:
            subject, body = email
            email_sent = send_email(subject, body)
        except Exception as e:
            print(f"Email failed: {e}", file=sys.stderr)
    else:
        print("No alert tomorrow — no email sent.")

    append_history(summary, telegram_sent, email_sent)


if __name__ == "__main__":
    main()
