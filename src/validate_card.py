from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--allow-warnings", action="store_true")
    args = parser.parse_args()

    with Image.open(args.image) as image:
        if image.size != (1080, 1350):
            raise SystemExit(f"Invalid image size: {image.size}; expected 1080x1350")
        if image.format != "JPEG":
            raise SystemExit(f"Invalid image format: {image.format}; expected JPEG")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    required = ["forecast_date", "weather_source", "venue"]
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        raise SystemExit(f"Missing manifest fields: {', '.join(missing)}")
    if manifest.get("warnings") and not args.allow_warnings:
        raise SystemExit("Validation warnings block publication: " + "; ".join(manifest["warnings"]))
    print("Card validation passed")


if __name__ == "__main__":
    main()

