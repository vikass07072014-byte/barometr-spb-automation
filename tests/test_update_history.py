from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from update_history import update_history  # noqa: E402


class UpdateHistoryTest(unittest.TestCase):
    def test_records_publication_idempotently(self) -> None:
        venues = [{"name": "DUO ASIA", "used_dates": ["2026-09-02"]}]
        manifest = {"forecast_date": "2026-09-02", "venue": {"name": "DUO ASIA"}}
        receipt = {"buffer_post_id": "123"}

        updated = update_history(venues, manifest, receipt)

        self.assertEqual(updated[0]["used_dates"], ["2026-09-02"])

    def test_requires_verified_publication_receipt(self) -> None:
        with self.assertRaisesRegex(ValueError, "buffer_post_id"):
            update_history(
                [{"name": "DUO ASIA"}],
                {"forecast_date": "2026-09-02", "venue": {"name": "DUO ASIA"}},
                {},
            )


if __name__ == "__main__":
    unittest.main()
