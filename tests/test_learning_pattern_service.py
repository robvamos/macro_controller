import unittest
from unittest.mock import patch

from services.learning_pattern_service import collect_learning_click_sequences, suggest_repeated_learning_patterns


class LearningPatternServiceTests(unittest.TestCase):
    def test_collect_learning_click_sequences_filters_learning_system_macros(self):
        macros = [
            {"id": 1, "nome": "learning", "system_key": "general_click_elements_learning"},
            {"id": 2, "nome": "regular", "system_key": None},
        ]
        events_by_macro = {
            1: [
                {"type": "mouse", "event": "down", "game_element_id": 10},
                {"type": "mouse", "event": "move"},
                {"type": "mouse", "event": "down", "game_element_id": 11},
            ],
            2: [{"type": "mouse", "event": "down", "game_element_id": 99}],
        }

        with (
            patch("services.learning_pattern_service.get_all_macros", return_value=macros),
            patch("services.learning_pattern_service.load_macro_events", side_effect=lambda macro_id: events_by_macro[macro_id]),
        ):
            sequences = collect_learning_click_sequences()

        self.assertEqual(len(sequences), 1)
        self.assertEqual(sequences[0]["element_ids"], (10, 11))

    def test_suggest_repeated_learning_patterns_returns_candidate_sequences(self):
        macros = [
            {"id": 1, "nome": "learning 1", "system_key": "general_click_elements_learning"},
            {"id": 2, "nome": "learning 2", "system_key": "general_click_elements_learning"},
        ]
        events_by_macro = {
            1: [
                {"type": "mouse", "event": "down", "game_element_id": 3},
                {"type": "mouse", "event": "down", "game_element_id": 4},
                {"type": "mouse", "event": "down", "game_element_id": 5},
            ],
            2: [
                {"type": "mouse", "event": "down", "game_element_id": 3},
                {"type": "mouse", "event": "down", "game_element_id": 4},
                {"type": "mouse", "event": "down", "game_element_id": 8},
            ],
        }

        with (
            patch("services.learning_pattern_service.get_all_macros", return_value=macros),
            patch("services.learning_pattern_service.load_macro_events", side_effect=lambda macro_id: events_by_macro[macro_id]),
        ):
            suggestions = suggest_repeated_learning_patterns(min_count=2, max_pattern_length=3)

        self.assertTrue(suggestions)
        self.assertEqual(suggestions[0].element_ids, (3, 4))
        self.assertEqual(suggestions[0].count, 2)
        self.assertIn(1, suggestions[0].source_macro_ids)
        self.assertIn(2, suggestions[0].source_macro_ids)


if __name__ == "__main__":
    unittest.main()
