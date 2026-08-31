from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import requests


CONDITION_TEXT = {
    "clear": "ЯСНО",
    "partly-cloudy": "ОБЛАЧНО С ПРОЯСНЕНИЯМИ",
    "cloudy": "ОБЛАЧНО",
    "overcast": "ПАСМУРНО",
    "drizzle": "НЕБОЛЬШОЙ ДОЖДЬ",
    "light-rain": "НЕБОЛЬШОЙ ДОЖДЬ",
    "rain": "ДОЖДЬ",
    "moderate-rain": "ДОЖДЬ",
    "heavy-rain": "СИЛЬНЫЙ ДОЖДЬ",
    "light-snow": "НЕБОЛЬШОЙ СНЕГ",
    "snow": "СНЕГ",
}


def part(forecast: dict, name: str) -> dict:
    return forecast.get("parts", {}).get(name) or {}


def normalize(payload: dict) -> dict:
    forecasts = payload.get("forecasts") or []
    if len(forecasts) < 2:
        raise ValueError("Yandex response must contain today and tomorrow")

    today, tomorrow = forecasts[0], forecasts[1]
    day_part = part(tomorrow, "day")
    night_part = part(tomorrow, "night")
    hours = tomorrow.get("hours") or []
    selected_hours = {"06", "09", "12", "15", "18", "21"}
    timeline = [
        {
            "hour": str(hour.get("hour", "")).zfill(2),
            "probability": int(hour.get("prec_prob") or 0),
        }
        for hour in hours
        if str(hour.get("hour", "")).zfill(2) in selected_hours
    ]
    if len(timeline) != 6:
        timeline = [{"hour": h, "probability": 0} for h in sorted(selected_hours)]

    condition = day_part.get("condition") or "cloudy"
    return {
        "source": "Яндекс Погода",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "today": {
            "date": today["date"],
            "morning": {
                "temp": part(today, "morning").get("temp_avg"),
                "condition": part(today, "morning").get("condition", "cloudy"),
            },
            "day": {
                "temp": part(today, "day").get("temp_avg"),
                "condition": part(today, "day").get("condition", "cloudy"),
            },
            "evening": {
                "temp": part(today, "evening").get("temp_avg"),
                "condition": part(today, "evening").get("condition", "cloudy"),
            },
        },
        "tomorrow": {
            "date": tomorrow["date"],
            "day_temp": day_part.get("temp_avg"),
            "night_temp": night_part.get("temp_avg"),
            "condition": condition,
            "condition_text": CONDITION_TEXT.get(condition, "ОБЛАЧНО"),
            "hourly_precipitation": timeline,
            "pressure_mm": day_part.get("pressure_mm"),
            "wind_speed": str(day_part.get("wind_speed", "—")).replace(".", ","),
            "wind_direction": str(day_part.get("wind_dir", "—")).upper(),
            "humidity": day_part.get("humidity"),
            "sunrise": tomorrow.get("sunrise", "—"),
            "sunset": tomorrow.get("sunset", "—"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lon", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    key = os.environ.get("YANDEX_WEATHER_API_KEY")
    if not key:
        raise SystemExit("YANDEX_WEATHER_API_KEY is not configured")

    response = requests.get(
        "https://api.weather.yandex.ru/v2/forecast",
        params={
            "lat": args.lat,
            "lon": args.lon,
            "lang": "ru_RU",
            "limit": 2,
            "hours": "true",
            "extra": "true",
        },
        headers={"X-Yandex-Weather-Key": key},
        timeout=20,
    )
    response.raise_for_status()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(normalize(response.json()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()

