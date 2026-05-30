import unittest
from unittest.mock import patch

from PIL import Image

from services.game_element_ingestion_service import (
    build_game_element_ingestion_guidelines,
    create_or_merge_game_element,
    build_prepared_asset_summary,
    build_game_element_description,
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
        self.assertTrue(any("esiste gia'" in line for line in guidelines))

    def test_create_or_merge_game_element_creates_new_element_when_catalog_is_empty(self):
        image = Image.new("RGB", (80, 40), color=(25, 50, 75))

        with (
            patch("services.game_element_ingestion_service.get_all_game_elements", return_value=[]),
            patch("services.game_element_ingestion_service.create_game_element", return_value=15) as create_game_element,
        ):
            result = create_or_merge_game_element(
                "Elemento Test",
                build_game_element_description("desc", "hint"),
                image,
                "PNG",
            )

        self.assertEqual(result.element_id, 15)
        self.assertEqual(result.element_name, "Elemento Test")
        self.assertFalse(result.reused_existing)
        create_game_element.assert_called_once()

    def test_create_or_merge_game_element_reuses_existing_similar_element(self):
        image = Image.new("RGB", (80, 40), color=(25, 50, 75))
        existing = {
            "id": 9,
            "nome": "Elemento Esistente",
            "descrizione": "Descrizione base",
            "immagine": b"blob",
            "formato_immagine": "PNG",
        }

        with (
            patch("services.game_element_ingestion_service.get_all_game_elements", return_value=[existing]),
            patch("services.game_element_ingestion_service.blob_to_image", return_value=image.copy()),
            patch("services.game_element_ingestion_service.update_game_element", return_value=True) as update_game_element,
            patch("services.game_element_ingestion_service.create_game_element") as create_game_element,
        ):
            result = create_or_merge_game_element(
                "Nuovo Nome",
                build_game_element_description("Nuovo contesto", "shared_button"),
                image,
                "PNG",
            )

        self.assertEqual(result.element_id, 9)
        self.assertEqual(result.element_name, "Elemento Esistente")
        self.assertTrue(result.reused_existing)
        self.assertTrue(result.updated_existing)
        create_game_element.assert_not_called()
        update_game_element.assert_called_once()


if __name__ == "__main__":
    unittest.main()
