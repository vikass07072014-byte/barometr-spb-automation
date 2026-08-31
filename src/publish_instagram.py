from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import requests


def post(url: str, data: dict) -> dict:
    response = requests.post(url, data=data, timeout=30)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True)
    parser.add_argument("--caption", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    if os.environ.get("AUTO_PUBLISH", "false").lower() != "true":
        raise SystemExit("AUTO_PUBLISH is not true; publication is intentionally blocked")
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    user_id = os.environ.get("INSTAGRAM_USER_ID")
    api_version = os.environ.get("META_API_VERSION", "v23.0")
    if not token or not user_id:
        raise SystemExit("INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID are required")

    caption = args.caption.read_text(encoding="utf-8")
    base = f"https://graph.instagram.com/{api_version}/{user_id}"
    container = post(
        f"{base}/media",
        {"image_url": args.image_url, "caption": caption, "access_token": token},
    )
    creation_id = container["id"]
    time.sleep(8)
    published = post(
        f"{base}/media_publish",
        {"creation_id": creation_id, "access_token": token},
    )
    receipt = {
        "container_id": creation_id,
        "media_id": published["id"],
        "image_url": args.image_url,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()

