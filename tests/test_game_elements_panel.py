import unittest

from ui.game_elements_panel import (
    compute_crop_display_size,
    map_display_selection_to_original,
)


class GameElementsPanelCropHelpersTests(unittest.TestCase):
    def test_compute_crop_display_size_preserves_ratio(self):
        self.assertEqual(compute_crop_display_size((1000, 500), (400, 300)), (400, 200))
        self.assertEqual(compute_crop_display_size((120, 80), (400, 300)), (120, 80))

    def test_map_display_selection_to_original_maps_back_to_source_pixels(self):
        mapped = map_display_selection_to_original(
            (10, 20, 110, 70),
            original_size=(400, 200),
            display_size=(200, 100),
        )
        self.assertEqual(mapped, (20, 40, 220, 140))

    def test_map_display_selection_to_original_clamps_and_normalizes(self):
        mapped = map_display_selection_to_original(
            (150, 80, -10, -5),
            original_size=(300, 150),
            display_size=(150, 75),
        )
        self.assertEqual(mapped, (0, 0, 300, 150))


if __name__ == "__main__":
    unittest.main()
