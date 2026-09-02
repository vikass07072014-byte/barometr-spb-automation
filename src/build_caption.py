from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def temp(value) -> str:
    return f"{int(value):+d}°"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weather", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    weather = json.loads(args.weather.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    forecast = weather["tomorrow"]
    venue = manifest["venue"]
    forecast_date = datetime.fromisoformat(forecast["date"]).strftime("%d.%m")
    caption = (
        f"Погода в Петербурге на {forecast_date} ☁️\n\n"
        f"Днём до {temp(forecast['day_temp'])}, ночью {temp(forecast['night_temp'])}. "
        f"{forecast['condition_text'].capitalize()}. Ветер {forecast['wind_speed']} м/с, "
        f"давление {forecast['pressure_mm']} мм рт. ст., влажность {forecast['humidity']}%.\n\n"
        f"Сегодня стоит заглянуть в {venue.get('display_name', venue['name'].title())}\n"
        f"📍 {venue['address']}\n"
        f"{venue['category_label']}: {venue['item']}\n\n"
        f"Данные: {weather['source']} — {weather.get('source_url', 'https://api.met.no/')}\n"
        "Данные обработаны «Барометром Петербурга». "
        f"Лицензия CC BY 4.0: {weather.get('license_url', 'https://creativecommons.org/licenses/by/4.0/')}\n\n"
        "#барометрпетербурга #погодаспб #санктпетербург #кудасходитьспб #рубинштейна"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(caption, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
