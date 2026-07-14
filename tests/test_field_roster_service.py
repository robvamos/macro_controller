import json
import tempfile
import unittest
from pathlib import Path

from doomsday.services.field_roster_service import (
    format_bench_and_plan,
    format_pair_details,
    load_field_roster,
    pair_row,
)


class FieldRosterServiceTests(unittest.TestCase):
    def test_load_default_field_roster_contains_current_and_recommended_pairs(self):
        roster = load_field_roster()

        self.assertEqual(len(roster["current_pairs"]), 5)
        self.assertEqual(len(roster["recommended_pairs"]), 5)
        self.assertEqual(roster["recommended_pairs"][0]["front_hero"], "Maxwell")
        self.assertEqual(roster["recommended_pairs"][0]["back_hero"], "Daryl")

    def test_formatters_keep_key_development_context_visible(self):
        roster = load_field_roster()
        details = format_pair_details(roster["recommended_pairs"][0])
        plan = format_bench_and_plan(roster)

        self.assertIn("Maxwell + Daryl", details)
        self.assertIn("Chasey", plan)
        self.assertIn("Maxwell", plan)
        self.assertIn("Metok Tso", plan)
        self.assertIn("non Maxwell + Metok Tso", plan)

    def test_pair_row_is_stable_for_treeview(self):
        pair = {
            "slot": 4,
            "front_hero": "Janet",
            "back_hero": "Daryl",
            "front_beast": "Vulcarhino",
            "support_beast": "Drago uragano",
            "role": "campo mobile",
        }

        self.assertEqual(
            pair_row(pair),
            (4, "Janet", "Daryl", "Vulcarhino", "Drago uragano", "campo mobile"),
        )

    def test_missing_roster_file_returns_empty_document(self):
        with tempfile.TemporaryDirectory() as tempdir:
            missing_path = Path(tempdir) / "missing.json"

            roster = load_field_roster(missing_path)

        self.assertEqual(roster["current_pairs"], [])
        self.assertEqual(roster["recommended_pairs"], [])

    def test_custom_roster_is_normalized(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "roster.json"
            path.write_text(json.dumps({"current_pairs": []}), encoding="utf-8")

            roster = load_field_roster(path)

        self.assertIn("recommended_pairs", roster)
        self.assertIn("development_plan", roster)


if __name__ == "__main__":
    unittest.main()
