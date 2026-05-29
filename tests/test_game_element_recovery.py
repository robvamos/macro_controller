import unittest
from unittest.mock import patch

from PIL import Image

from doomsday.vision.game_element_recovery import GameElementMatch, find_best_scaled_match


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
            threshold=0.8,
            scales=(1.0, 1.1, 1.2),
        )

        self.assertIsInstance(match, GameElementMatch)
        self.assertGreaterEqual(match.score, 0.8)
        self.assertEqual(match.scale, 1.2)
        self.assertTrue(1080 <= match.center[0] <= 1095)
        self.assertTrue(570 <= match.center[1] <= 585)


if __name__ == "__main__":
    unittest.main()
