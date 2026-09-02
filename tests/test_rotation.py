from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from render_card import choose_venue  # noqa: E402


class VenueRotationTest(unittest.TestCase):
    def test_blocks_recent_repeat(self) -> None:
        venues = [
            {
                "name": "USED",
                "category": "food",
                "ready": True,
                "image": "used.png",
                "used_dates": ["2026-08-30"],
            }
        ]
        with self.assertRaisesRegex(ValueError, "instead of repeating"):
            choose_venue(venues, "2026-09-02", ["food"], strict=False)

    def test_selects_unused_venue_in_required_category(self) -> None:
        venues = [
            {
                "name": "NEW",
                "category": "non_alcoholic_drink",
                "ready": True,
                "image": "new.png",
            }
        ]
        venue, warnings = choose_venue(
            venues,
            "2026-09-02",
            ["non_alcoholic_drink"],
            strict=True,
        )
        self.assertEqual(venue["name"], "NEW")
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
