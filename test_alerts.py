"""Send TEST alerts as if conditions were met, without touching APIs.

Builds a fake summary with great alert windows for several spots, formats
the same Telegram and email messages the daily script would, prepends a
clear TEST marker, and delivers via the same credentials.
"""

import sys

from check_kite import (
    format_friend_email,
    format_telegram_message,
    send_email,
    send_telegram,
)

FAKE_SUMMARY = {
    "generated_at": "TEST",
    "today": "2026-XX-XX (test)",
    "tomorrow": "2026-XX-XY (test)",
    "sources": ["open_meteo", "gem", "met_norway"],
    "spots": [
        {
            "name": "Oka",
            "lat": 45.4667, "lon": -74.0833,
            "allowed_dirs": ["O", "SO", "S", "NO"],
            "alerts": {
                "today": {
                    "open_meteo": {"start": "13:00", "end": "17:00", "hours": 5,
                                   "wind_min": 15, "wind_max": 22, "dominant_dir": "SO"},
                    "gem": None,
                    "met_norway": {"start": "14:00", "end": "16:00", "hours": 3,
                                   "wind_min": 13, "wind_max": 18, "dominant_dir": "S"},
                },
                "tomorrow": {
                    "open_meteo": {"start": "11:00", "end": "16:00", "hours": 6,
                                   "wind_min": 16, "wind_max": 24, "dominant_dir": "O"},
                    "gem": {"start": "12:00", "end": "15:00", "hours": 4,
                            "wind_min": 14, "wind_max": 20, "dominant_dir": "O"},
                    "met_norway": None,
                },
            },
        },
        {
            "name": "Saint-Zotique",
            "lat": 45.2500, "lon": -74.2500,
            "allowed_dirs": ["SO", "S", "SE", "O"],
            "alerts": {
                "today": {"open_meteo": None, "gem": None, "met_norway": None},
                "tomorrow": {
                    "open_meteo": {"start": "13:00", "end": "17:00", "hours": 5,
                                   "wind_min": 14, "wind_max": 19, "dominant_dir": "SO"},
                    "gem": None,
                    "met_norway": None,
                },
            },
        },
    ],
}


def main():
    print("=== TEST alert delivery (no real API calls) ===\n")

    msg = format_telegram_message(FAKE_SUMMARY)
    if msg:
        prefixed = "🧪 *CECI EST UN TEST* 🧪\n\n" + msg
        print("--- Telegram message ---")
        print(prefixed)
        print()
        try:
            send_telegram(prefixed)
        except Exception as e:
            print(f"Telegram send failed: {e}", file=sys.stderr)
    else:
        print("No telegram message produced from fake summary (bug).")

    email = format_friend_email(FAKE_SUMMARY)
    if email:
        subject, body = email
        test_subject = "🧪 TEST — " + subject
        test_body = (
            "🧪 CECI EST UN TEST — pas de vraies prévisions, juste un test "
            "du système de notification.\n\n" + body
        )
        print("\n--- Email ---")
        print(f"Subject: {test_subject}\n")
        print(test_body)
        print()
        try:
            send_email(test_subject, test_body)
        except Exception as e:
            print(f"Email send failed: {e}", file=sys.stderr)
    else:
        print("No email produced from fake summary (bug).")

    print("\n=== Test complete ===")


if __name__ == "__main__":
    main()
