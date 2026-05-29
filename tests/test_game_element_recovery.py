import unittest
from unittest.mock import patch

from PIL import Image

from doomsday.vision.game_element_recovery import (
    GameElementMatch,
    find_best_scaled_match,
    search_game_window_elements,
)


class GameElementRecoveryTests(unittest.TestCase):
    def test_find_best_scaled_match_detects_scaled_element(self):
        template = Image.new("RGB", (20, 20), color=(0, 0, 0))
        for x in range(4, 16):
            for y in range(4, 16):
                template.putpixel((x, y), (255, 220, 120))

        screenshot = Image.new("RGB", (220, 180), color=(10, 10, 10))
        scaled_template = template.resize((24, 24))
        screenshot.paste(scaled_template, (80, 60))

        with (
            patch("doomsday.vision.game_element_recovery.get_game_element_by_name", return_value=None),
        ):
            from doomsday.vision.game_element_recovery import _to_cv_grayscale

            template_gray = _to_cv_grayscale(template)
            screenshot_gray = _to_cv_grayscale(screenshot)

        match = find_best_scaled_match(
            "popup-close",
            template_gray,
            screenshot_gray,
            window_rect=(1000, 500, 1220, 680),
            threshold=0.85,
            scales=(1.0, 1.1, 1.2),
        )

        self.assertIsInstance(match, GameElementMatch)
        self.assertGreaterEqual(match.score, 0.85)
        self.assertEqual(match.scale, 1.2)
        self.assertTrue(1080 <= match.center[0] <= 1095)
        self.assertTrue(570 <= match.center[1] <= 585)

    def test_search_game_window_elements_returns_common_found_result(self):
        fake_match = GameElementMatch(
            element_name="popup_exit_close_symbol",
            score=0.91,
            location=(100, 120),
            size=(30, 30),
            center=(115, 135),
            scale=1.0,
        )

        with patch(
            "doomsday.vision.game_element_recovery.find_game_element_match",
            side_effect=[None, fake_match],
        ):
            result = search_game_window_elements(
                (0, 0, 1920, 1080),
                element_names=("other_symbol", "popup_exit_close_symbol"),
                threshold=0.85,
            )

        self.assertTrue(result.found)
        self.assertTrue(result.condition_satisfied)
        self.assertEqual(result.matched_element_name, "popup_exit_close_symbol")
        self.assertEqual(result.center, (115, 135))
        self.assertEqual(result.requested_elements, ("other_symbol", "popup_exit_close_symbol"))

    def test_search_game_window_elements_supports_non_presence_condition(self):
        with patch(
            "doomsday.vision.game_element_recovery.find_game_element_match",
            return_value=None,
        ):
            result = search_game_window_elements(
                (0, 0, 1920, 1080),
                element_names=("blocking_popup",),
                threshold=0.85,
                expected_presence=False,
            )

        self.assertFalse(result.found)
        self.assertTrue(result.condition_satisfied)
        self.assertIsNone(result.center)


if __name__ == "__main__":
    unittest.main()
