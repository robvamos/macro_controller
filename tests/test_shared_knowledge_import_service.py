import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.shared_knowledge_import_service import (
    SHARED_ELEMENT_MARKER,
    SHARED_IMAGE_MARKER,
    import_shared_game_elements,
)


class SharedKnowledgeImportServiceTests(unittest.TestCase):
    def test_import_adds_shared_variants_without_overwriting_local_elements(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            declared_image_hashes = ["a" * 64, "b" * 64]
            (root / "game_elements").mkdir()
            (root / "game_elements" / "first.png").write_bytes(b"first image")
            (root / "game_elements" / "second.png").write_bytes(b"second image")
            (root / "game_elements_manifest.json").write_text(
                json.dumps(
                    {
                        "game_elements": [
                            {
                                "id": 14,
                                "name": "Shared Button",
                                "description": "A shared visual control",
                                "image_path": "game_elements/first.png",
                                "image_paths": [
                                    "game_elements/first.png",
                                    "game_elements/second.png",
                                ],
                                "image_hash": declared_image_hashes[0],
                                "image_hashes": declared_image_hashes,
                                "metadata_blocks": {},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            local_elements = [
                {
                    "id": 1,
                    "nome": "Shared Button",
                    "descrizione": "Workstation-specific note",
                    "immagine": b"local image",
                    "formato_immagine": "PNG",
                }
            ]
            next_id = 2

            def create(name, description, image_blob, image_format):
                nonlocal next_id
                element = {
                    "id": next_id,
                    "nome": name,
                    "descrizione": description,
                    "immagine": image_blob,
                    "formato_immagine": image_format,
                }
                next_id += 1
                local_elements.append(element)
                return element["id"]

            with (
                patch(
                    "services.shared_knowledge_import_service.get_all_game_elements",
                    return_value=local_elements,
                ),
                patch(
                    "services.shared_knowledge_import_service.create_game_element",
                    side_effect=create,
                ) as create_mock,
                patch("services.shared_knowledge_import_service.update_game_element") as update_mock,
            ):
                result = import_shared_game_elements(root)
                self.assertEqual(result["imported"], 2)
                self.assertEqual(result["missing_images"], 0)
                self.assertEqual(create_mock.call_count, 2)
                self.assertEqual(update_mock.call_count, 0)
                self.assertEqual(local_elements[0]["descrizione"], "Workstation-specific note")
                imported = local_elements[1:]
                self.assertEqual([item["nome"] for item in imported], ["Shared Button_2", "Shared Button_3"])
                for element in imported:
                    self.assertIn(f"{SHARED_ELEMENT_MARKER} 14", element["descrizione"])
                    self.assertIn(SHARED_IMAGE_MARKER, element["descrizione"])
                self.assertIn(f"{SHARED_IMAGE_MARKER} {declared_image_hashes[0]}", imported[0]["descrizione"])
                self.assertIn(f"{SHARED_IMAGE_MARKER} {declared_image_hashes[1]}", imported[1]["descrizione"])

                repeated = import_shared_game_elements(root)
                self.assertEqual(repeated["imported"], 0)
                self.assertEqual(repeated["updated"], 0)
                self.assertEqual(repeated["skipped"], 2)
                self.assertEqual(create_mock.call_count, 2)
                self.assertEqual(update_mock.call_count, 0)


if __name__ == "__main__":
    unittest.main()
