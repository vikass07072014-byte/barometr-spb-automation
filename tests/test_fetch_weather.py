from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fetch_weather import amount_mm, normalize, timeline_precipitation  # noqa: E402


def point(time: str, temp: float, symbol: str, rain: float = 0) -> dict:
    return {
        "time": time,
        "data": {
            "instant": {
                "details": {
                    "air_temperature": temp,
                    "air_pressure_at_sea_level": 1006.5,
                    "relative_humidity": 72,
                    "wind_speed": 3.2,
                    "wind_from_direction": 315,
                }
            },
            "next_1_hours": {
                "summary": {"symbol_code": symbol},
                "details": {"precipitation_amount": rain},
            },
        },
    }


class NormalizeTest(unittest.TestCase):
    def test_can_build_card_for_specific_forecast_date(self) -> None:
        now = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
        timeseries = []
        for day in (2, 3):
            for hour in range(24):
                timeseries.append(
                    point(
                        f"2026-09-{day:02d}T{hour:02d}:00:00+03:00",
                        15 + hour / 4,
                        "partlycloudy_day",
                    )
                )
        payload = {"properties": {"timeseries": timeseries}}
        sun = {
            "properties": {
                "sunrise": {"time": "2026-09-03T05:57:00+03:00"},
                "sunset": {"time": "2026-09-03T19:56:00+03:00"},
            }
        }

        result = normalize(
            payload,
            sun,
            "Europe/Moscow",
            now=now,
            forecast_date=date(2026, 9, 3),
        )

        self.assertEqual(result["today"]["date"], "2026-09-02")
        self.assertEqual(result["tomorrow"]["date"], "2026-09-03")

    def test_normalizes_met_forecast_into_card_contract(self) -> None:
        timeseries = []
        for day in (31,):
            for hour in (6, 9, 12, 15, 18, 21):
                timeseries.append(point(f"2026-08-{day:02d}T{hour-3:02d}:00:00Z", 17 + hour / 10, "cloudy"))
        for hour in range(24):
            rain = 0.4 if hour in (9, 12) else 0
            symbol = "lightrainshowers_day" if rain else "partlycloudy_day"
            timeseries.append(point(f"2026-09-01T{(hour-3)%24:02d}:00:00Z", 14 + hour / 3, symbol, rain))

        # Correct the UTC date for the first three local hours of 1 September.
        for hour in range(3):
            timeseries[-24 + hour]["time"] = f"2026-08-31T{21+hour:02d}:00:00Z"

        forecast = {"properties": {"timeseries": timeseries}}
        sun = {
            "properties": {
                "sunrise": {"time": "2026-09-01T05:53:00+03:00"},
                "sunset": {"time": "2026-09-01T20:04:00+03:00"},
            }
        }
        result = normalize(
            forecast,
            sun,
            "Europe/Moscow",
            now=datetime(2026, 8, 31, 6, 20, tzinfo=ZoneInfo("Europe/Moscow")),
        )

        self.assertEqual(result["source"], "MET Norway")
        self.assertTrue(result["data_modified"])
        self.assertIn("creativecommons.org", result["license_url"])
        self.assertEqual(result["tomorrow"]["date"], "2026-09-01")
        self.assertEqual(result["tomorrow"]["condition"], "light-rain")
        self.assertEqual(result["tomorrow"]["condition_text"], "НЕБОЛЬШОЙ ДОЖДЬ • КРАТКОВРЕМЕННО")
        self.assertEqual(result["tomorrow"]["pressure_mm"], 755)
        self.assertEqual(result["tomorrow"]["wind_direction"], "СЗ")
        self.assertEqual(result["tomorrow"]["sunrise"], "05:53")
        self.assertEqual(
            result["tomorrow"]["hourly_precipitation"][1],
            {"hour": "09", "amount_mm": 0.4, "has_precipitation": True},
        )

    def test_rejects_response_without_tomorrow(self) -> None:
        forecast = {
            "properties": {
                "timeseries": [point("2026-08-31T06:00:00Z", 17, "cloudy")]
            }
        }
        with self.assertRaisesRegex(ValueError, "today and tomorrow"):
            normalize(
                forecast,
                {},
                "Europe/Moscow",
                now=datetime(2026, 8, 31, 6, 20, tzinfo=ZoneInfo("Europe/Moscow")),
            )

    def test_does_not_label_six_hour_accumulation_as_hourly(self) -> None:
        six_hour_point = point("2026-09-01T09:00:00Z", 18, "rain")
        six_hour_point["data"].pop("next_1_hours")
        six_hour_point["data"]["next_6_hours"] = {
            "summary": {"symbol_code": "rain"},
            "details": {"precipitation_amount": 6.0},
        }
        self.assertEqual(amount_mm(six_hour_point), 0.0)
        self.assertEqual(
            timeline_precipitation(six_hour_point),
            {"has_precipitation": True, "label": "ДОЖДЬ", "resolution_hours": 6},
        )


if __name__ == "__main__":
    unittest.main()
