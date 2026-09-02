from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path


def update_history(venues: list[dict], manifest: dict, receipt: dict) -> list[dict]:
    if not receipt.get("buffer_post_id"):
        raise ValueError("Schedule receipt has no buffer_post_id")

    forecast_date = manifest["forecast_date"]
    venue_name = manifest["venue"]["name"]
    cutoff = date.fromisoformat(forecast_date) - timedelta(days=90)

    for venue in venues:
        if venue["name"] != venue_name:
            continue
        used_dates = {
            raw_date
            for raw_date in venue.get("used_dates", [])
            if date.fromisoformat(raw_date) >= cutoff
        }
        used_dates.add(forecast_date)
        venue["used_dates"] = sorted(used_dates)
        return venues

    raise ValueError(f"Published venue is missing from database: {venue_name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--venues", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    venues = json.loads(args.venues.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    updated = update_history(venues, manifest, receipt)
    args.venues.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {manifest['venue']['name']} for {manifest['forecast_date']}")


if __name__ == "__main__":
    main()
