import unittest

from PIL import Image

from services.game_element_ingestion_service import (
    build_game_element_ingestion_guidelines,
    build_prepared_asset_summary,
    prepare_game_element_asset,
)


class GameElementIngestionServiceTests(unittest.TestCase):
    def test_prepare_game_element_asset_preserves_size_and_uses_lossless_png(self):
        image = Image.new("RGB", (123, 45), color=(120, 80, 20))

        asset = prepare_game_element_asset(image, source_format="JPEG", semantic_hint="popup close button")

        self.assertEqual(asset.original_size, (123, 45))
        self.assertEqual(asset.stored_size, (123, 45))
        self.assertEqual(asset.storage_format, "PNG")
        self.assertEqual(asset.original_format, "JPEG")
        self.assertEqual(asset.semantic_hint, "popup close button")
        self.assertIn("aspect_ratio_preserved", asset.notes)

    def test_guidelines_and_summary_are_user_facing(self):
        image = Image.new("RGBA", (64, 64), color=(255, 255, 255, 0))
        asset = prepare_game_element_asset(image, source_format="PNG", semantic_hint="shared top-left panel")

        guidelines = build_game_element_ingestion_guidelines()
        summary = build_prepared_asset_summary(asset)

        self.assertGreaterEqual(len(guidelines), 5)
        self.assertIn("senza distorsioni", summary)
        self.assertIn("shared top-left panel", summary)
        self.assertTrue(any("cambiare lingua" in line for line in guidelines))
        self.assertTrue(any("badge rossi" in line for line in guidelines))


if __name__ == "__main__":
    unittest.main()
