from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from publish_buffer import create_scheduled_post, resolve_due_at  # noqa: E402


class BufferSchedulingTest(unittest.TestCase):
    def test_resolves_moscow_publish_time_to_utc(self) -> None:
        now = datetime(2026, 9, 1, 4, 50, tzinfo=timezone.utc)

        due_at = resolve_due_at("08:00", "Europe/Moscow", now=now)

        self.assertEqual(due_at, "2026-09-01T05:00:00Z")

    def test_delayed_workflow_uses_minimum_lead_time(self) -> None:
        now = datetime(2026, 9, 1, 5, 5, tzinfo=timezone.utc)

        due_at = resolve_due_at("08:00", "Europe/Moscow", now=now)

        self.assertEqual(due_at, "2026-09-01T05:07:00Z")

    @patch("publish_buffer.request_graphql")
    def test_creates_automatic_instagram_image_post(self, request_graphql) -> None:
        request_graphql.return_value = {
            "createPost": {
                "__typename": "PostActionSuccess",
                "post": {
                    "id": "buffer-post-1",
                    "dueAt": "2026-09-01T05:00:00Z",
                    "status": "buffer",
                },
            }
        }

        post = create_scheduled_post(
            "token",
            "channel-1",
            "https://example.com/card.jpg",
            "Caption",
            "2026-09-01T05:00:00Z",
        )

        self.assertEqual(post["id"], "buffer-post-1")
        variables = request_graphql.call_args.args[3]
        self.assertEqual(variables["input"]["mode"], "customScheduled")
        self.assertEqual(variables["input"]["schedulingType"], "automatic")
        self.assertEqual(
            variables["input"]["assets"][0]["image"]["url"],
            "https://example.com/card.jpg",
        )
        self.assertEqual(variables["input"]["metadata"]["instagram"]["type"], "post")

    @patch("publish_buffer.request_graphql")
    def test_raises_when_buffer_rejects_post(self, request_graphql) -> None:
        request_graphql.return_value = {
            "createPost": {"__typename": "PostInvalidInputError", "message": "bad image"}
        }

        with self.assertRaisesRegex(RuntimeError, "bad image"):
            create_scheduled_post(
                "token",
                "channel-1",
                "https://example.com/card.jpg",
                "Caption",
                "2026-09-01T05:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
