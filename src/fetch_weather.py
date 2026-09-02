from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


LOCATIONFORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
SUNRISE_URL = "https://api.met.no/weatherapi/sunrise/3.0/sun"
DEFAULT_USER_AGENT = (
    "barometr-spb/1.0 "
    "(+https://github.com/vikass07072014-byte/barometr-spb-automation)"
)
TIMELINE_HOURS = (6, 9, 12, 15, 18, 21)


def parse_time(value: str, timezone: ZoneInfo) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone)


def symbol_condition(symbol: str) -> str:
    value = (symbol or "cloudy").lower()
    if "heavyrain" in value:
        return "heavy-rain"
    if "rain" in value or "sleet" in value:
        return "light-rain" if "light" in value else "rain"
    if "snow" in value:
        return "light-snow" if "light" in value else "snow"
    if "clearsky" in value:
        return "clear"
    if "fair" in value or "partlycloudy" in value:
        return "partly-cloudy"
    if "fog" in value:
        return "cloudy"
    return "cloudy" if "cloudy" in value else "overcast"


def compass_ru(degrees: float | int | None) -> str:
    if degrees is None:
        return "—"
    labels = ("С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ")
    return labels[int((float(degrees) + 22.5) // 45) % 8]


def instant(point: dict) -> dict:
    return point.get("data", {}).get("instant", {}).get("details", {})


def period(point: dict) -> dict:
    data = point.get("data", {})
    for key in ("next_1_hours", "next_6_hours", "next_12_hours"):
        if data.get(key):
            return data[key]
    return {}


def amount_mm(point: dict) -> float:
    # The card timeline is explicitly hourly. Do not present a 6- or 12-hour
    # accumulation as if it belonged to one hour when next_1_hours is absent.
    details = point.get("data", {}).get("next_1_hours", {}).get("details", {})
    value = details.get("precipitation_amount", 0)
    return round(float(value or 0), 1)


def forecast_amount_mm(point: dict) -> float:
    data = point.get("data", {})
    for key in ("next_1_hours", "next_6_hours", "next_12_hours"):
        if data.get(key):
            value = data[key].get("details", {}).get("precipitation_amount", 0)
            return round(float(value or 0), 1)
    return 0.0


def timeline_precipitation(point: dict) -> dict:
    data = point.get("data", {})
    if data.get("next_1_hours"):
        amount = amount_mm(point)
        return {
            "amount_mm": amount,
            "has_precipitation": amount >= 0.1 or "rain" in symbol_condition(point_symbol(point)),
        }
    for hours in (6, 12):
        block = data.get(f"next_{hours}_hours", {})
        if block:
            amount = round(float(block.get("details", {}).get("precipitation_amount", 0) or 0), 1)
            condition = symbol_condition(block.get("summary", {}).get("symbol_code", "cloudy"))
            has_precipitation = amount >= 0.1 or "rain" in condition or "snow" in condition
            return {
                "has_precipitation": has_precipitation,
                "label": "ДОЖДЬ" if has_precipitation else "—",
                "resolution_hours": hours,
            }
    return {"has_precipitation": False, "label": "—"}


def point_symbol(point: dict) -> str:
    return period(point).get("summary", {}).get("symbol_code", "cloudy")


def closest(points: list[tuple[datetime, dict]], hour: int) -> tuple[datetime, dict]:
    if not points:
        raise ValueError("Forecast day has no hourly points")
    return min(points, key=lambda item: abs(item[0].hour - hour))


def period_summary(points: list[tuple[datetime, dict]], hour: int) -> dict:
    _, point = closest(points, hour)
    details = instant(point)
    return {
        "temp": round(float(details.get("air_temperature", 0))),
        "condition": symbol_condition(point_symbol(point)),
    }


def condition_summary(points: list[tuple[datetime, dict]]) -> tuple[str, str]:
    daytime = [item for item in points if 8 <= item[0].hour <= 21]
    if not daytime:
        daytime = points
    amounts = [forecast_amount_mm(point) for _, point in daytime]
    conditions = [symbol_condition(point_symbol(point)) for _, point in daytime]
    total = round(sum(amounts), 1)

    if any(condition in {"snow", "light-snow"} for condition in conditions):
        return "light-snow", "НЕБОЛЬШОЙ СНЕГ • КРАТКОВРЕМЕННО"
    if total >= 3:
        return "rain", "ДОЖДЬ • ПЕРИОДАМИ"
    if total >= 0.1 or any("rain" in condition for condition in conditions):
        return "light-rain", "НЕБОЛЬШОЙ ДОЖДЬ • КРАТКОВРЕМЕННО"

    common = Counter(conditions).most_common(1)[0][0]
    if "partly-cloudy" in conditions or ({"clear", "cloudy"} <= set(conditions)):
        return "partly-cloudy", "ОБЛАЧНО С ПРОЯСНЕНИЯМИ"
    texts = {
        "clear": "ЯСНО",
        "cloudy": "ОБЛАЧНО",
        "overcast": "ПАСМУРНО",
    }
    return common, texts.get(common, "ОБЛАЧНО")


def solar_time(payload: dict, key: str, timezone: ZoneInfo) -> str:
    value = payload.get("properties", {}).get(key, {}).get("time")
    return parse_time(value, timezone).strftime("%H:%M") if value else "—"


def normalize(
    forecast_payload: dict,
    sunrise_payload: dict,
    timezone_name: str,
    now: datetime | None = None,
    forecast_date: date | None = None,
) -> dict:
    timezone = ZoneInfo(timezone_name)
    current = now.astimezone(timezone) if now else datetime.now(timezone)
    tomorrow_date = forecast_date or (current.date() + timedelta(days=1))
    today_date = tomorrow_date - timedelta(days=1)

    grouped: dict = {}
    for point in forecast_payload.get("properties", {}).get("timeseries", []):
        local_time = parse_time(point["time"], timezone)
        grouped.setdefault(local_time.date(), []).append((local_time, point))

    today_points = grouped.get(today_date, [])
    tomorrow_points = grouped.get(tomorrow_date, [])
    if not today_points or not tomorrow_points:
        raise ValueError("MET Norway response must contain today and tomorrow")

    day_points = [item for item in tomorrow_points if 9 <= item[0].hour <= 18]
    night_points = [item for item in tomorrow_points if item[0].hour <= 6 or item[0].hour >= 22]
    if not day_points or not night_points:
        raise ValueError("MET Norway response has incomplete tomorrow periods")
    day_temp = max(float(instant(point).get("air_temperature", 0)) for _, point in day_points)
    night_temp = min(float(instant(point).get("air_temperature", 0)) for _, point in night_points)
    _, day_point = closest(tomorrow_points, 14)
    day_details = instant(day_point)
    condition, condition_text = condition_summary(tomorrow_points)

    timeline = []
    for hour in TIMELINE_HOURS:
        _, point = closest(tomorrow_points, hour)
        timeline.append({"hour": f"{hour:02d}", **timeline_precipitation(point)})

    return {
        "source": "MET Norway",
        "source_url": "https://api.met.no/",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "data_modified": True,
        "generated_at": current.isoformat(timespec="seconds"),
        "today": {
            "date": today_date.isoformat(),
            "morning": period_summary(today_points, 9),
            "day": period_summary(today_points, 15),
            "evening": period_summary(today_points, 20),
        },
        "tomorrow": {
            "date": tomorrow_date.isoformat(),
            "day_temp": round(day_temp),
            "night_temp": round(night_temp),
            "condition": condition,
            "condition_text": condition_text,
            "hourly_precipitation": timeline,
            "pressure_mm": round(float(day_details.get("air_pressure_at_sea_level", 0)) * 0.750061683),
            "wind_speed": str(round(float(day_details.get("wind_speed", 0)), 1)).replace(".", ","),
            "wind_direction": compass_ru(day_details.get("wind_from_direction")),
            "humidity": round(float(day_details.get("relative_humidity", 0))),
            "sunrise": solar_time(sunrise_payload, "sunrise", timezone),
            "sunset": solar_time(sunrise_payload, "sunset", timezone),
        },
    }


def session() -> requests.Session:
    retry = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    client = requests.Session()
    client.mount("https://", HTTPAdapter(max_retries=retry))
    client.headers.update({"User-Agent": os.environ.get("MET_USER_AGENT", DEFAULT_USER_AGENT)})
    return client


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lon", required=True, type=float)
    parser.add_argument("--timezone", default="Europe/Moscow")
    parser.add_argument("--forecast-date", type=date.fromisoformat)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    timezone = ZoneInfo(args.timezone)
    tomorrow = args.forecast_date or (datetime.now(timezone).date() + timedelta(days=1))
    client = session()
    forecast = client.get(
        LOCATIONFORECAST_URL,
        params={"lat": round(args.lat, 4), "lon": round(args.lon, 4)},
        timeout=20,
    )
    forecast.raise_for_status()
    sunrise = client.get(
        SUNRISE_URL,
        params={
            "lat": round(args.lat, 4),
            "lon": round(args.lon, 4),
            "date": tomorrow.isoformat(),
            "offset": "+03:00",
        },
        timeout=20,
    )
    sunrise.raise_for_status()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            normalize(
                forecast.json(),
                sunrise.json(),
                args.timezone,
                forecast_date=tomorrow,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
