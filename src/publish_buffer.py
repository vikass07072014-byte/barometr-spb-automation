from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


BUFFER_API_URL = "https://api.buffer.com"

CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess {
      post {
        id
        text
        dueAt
        status
        assets {
          id
          mimeType
        }
      }
    }
    ... on MutationError {
      message
    }
  }
}
"""


def request_graphql(api_url: str, token: str, query: str, variables: dict) -> dict:
    response = requests.post(
        api_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"Buffer GraphQL request failed: {payload['errors']}")
    return payload["data"]


def resolve_due_at(
    publish_time: str,
    timezone_name: str,
    publish_date: date | None = None,
    now: datetime | None = None,
    minimum_lead_minutes: int = 2,
) -> str:
    local_timezone = ZoneInfo(timezone_name)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    hour, minute = (int(part) for part in publish_time.split(":"))
    local_now = current.astimezone(local_timezone)
    target_date = publish_date or local_now.date()
    local_target = datetime.combine(target_date, datetime.min.time(), local_timezone).replace(
        hour=hour,
        minute=minute,
    )
    target = local_target.astimezone(timezone.utc)
    minimum_target = current + timedelta(minutes=minimum_lead_minutes)
    if target < minimum_target:
        if publish_date is not None:
            raise ValueError("Requested publish date/time is in the past or too close")
        target = minimum_target
    return target.isoformat(timespec="seconds").replace("+00:00", "Z")


def create_scheduled_post(
    token: str,
    channel_id: str,
    image_url: str,
    caption: str,
    due_at: str,
    api_url: str = BUFFER_API_URL,
) -> dict:
    variables = {
        "input": {
            "text": caption,
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": due_at,
            "aiAssisted": True,
            "assets": [
                {
                    "image": {
                        "url": image_url,
                        "metadata": {
                            "altText": "Прогноз погоды Барометр Петербурга"
                        },
                    }
                }
            ],
            "metadata": {
                "instagram": {
                    "type": "post",
                    "shouldShareToFeed": True,
                    "isAiGenerated": True,
                }
            },
        }
    }
    data = request_graphql(api_url, token, CREATE_POST_MUTATION, variables)
    result = data["createPost"]
    if result.get("__typename") != "PostActionSuccess":
        raise RuntimeError(f"Buffer rejected the post: {result.get('message', result)}")
    return result["post"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True)
    parser.add_argument("--caption", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--publish-time", default="08:00")
    parser.add_argument("--publish-date", type=date.fromisoformat)
    parser.add_argument("--timezone", default="Europe/Moscow")
    args = parser.parse_args()

    if os.environ.get("AUTO_PUBLISH", "false").lower() != "true":
        raise SystemExit("AUTO_PUBLISH is not true; publication is intentionally blocked")
    token = os.environ.get("BUFFER_API_KEY")
    channel_id = os.environ.get("BUFFER_CHANNEL_ID")
    if not token or not channel_id:
        raise SystemExit("BUFFER_API_KEY and BUFFER_CHANNEL_ID are required")

    caption = args.caption.read_text(encoding="utf-8")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    due_at = resolve_due_at(args.publish_time, args.timezone, publish_date=args.publish_date)
    post = create_scheduled_post(token, channel_id, args.image_url, caption, due_at)
    receipt = {
        "provider": "buffer",
        "buffer_post_id": post["id"],
        "status": post.get("status"),
        "scheduled_for": post.get("dueAt") or due_at,
        "image_url": args.image_url,
        "forecast_date": manifest["forecast_date"],
        "venue": manifest["venue"]["name"],
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
