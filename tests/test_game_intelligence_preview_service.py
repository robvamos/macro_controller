import unittest

from services.game_intelligence_preview_service import (
    build_game_plan_preview,
    format_game_plan_summary,
    format_plan_step_details,
    parse_preview_facts,
    plan_step_rows,
)


class GameIntelligencePreviewServiceTests(unittest.TestCase):
    def test_parse_preview_facts_requires_json_object(self):
        self.assertEqual(parse_preview_facts('{"ui.observed": true}'), {"ui.observed": True})
        with self.assertRaises(ValueError):
            parse_preview_facts("[]")

    def test_preview_is_read_only_and_exposes_plan_steps(self):
        preview = build_game_plan_preview("migliora in Arena della Gloria senza spendere gemme")

        self.assertIn("interpretation", preview)
        self.assertIn("plan", preview)
        self.assertTrue(plan_step_rows(preview))
        self.assertIn("Modalita:", format_game_plan_summary(preview))
        self.assertIn("Stato:", format_plan_step_details(preview, 0))

    def test_empty_goal_is_rejected(self):
        with self.assertRaises(ValueError):
            build_game_plan_preview("  ")


if __name__ == "__main__":
    unittest.main()
