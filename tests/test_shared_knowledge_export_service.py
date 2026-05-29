import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from game_elements import image_to_blob
from services.shared_knowledge_export_service import (
    export_shared_knowledge,
    parse_game_element_description,
    slugify,
)


class SharedKnowledgeExportServiceTests(unittest.TestCase):
    def test_parse_game_element_description_extracts_embedded_metadata(self):
        description = (
            "Bottone chiusura popup.\n"
            "AUTO_CLICK_ELEMENT_METADATA:{\"ui_node_id\":\"initial_blocking_popup_close_symbol\"}\n\n"
            "MEMORIA SEMANTICA: chiude spesso popup bloccanti."
        )

        parsed = parse_game_element_description(description)

        self.assertEqual(parsed["plain_description"], "Bottone chiusura popup.")
        self.assertEqual(
            parsed["metadata_blocks"]["auto_click_element_metadata"][0]["ui_node_id"],
            "initial_blocking_popup_close_symbol",
        )
        self.assertEqual(parsed["memory_note"], "chiude spesso popup bloccanti.")

    def test_slugify_keeps_stable_ascii_names(self):
        self.assertEqual(slugify("Boot Popup: Chiudi!"), "boot_popup_chiudi")
        self.assertEqual(slugify(""), "element")

    def test_export_shared_knowledge_writes_manifest_sessions_and_images(self):
        image_blob = image_to_blob(Image.new("RGB", (12, 8), "red"))
        element = {
            "id": 7,
            "nome": "Popup Close",
            "descrizione": "Close button",
            "formato_immagine": "PNG",
            "data_creazione": "2026-05-29 10:00:00",
            "data_ultima_modifica": "2026-05-29 10:01:00",
        }
        full_element = {**element, "immagine": image_blob}
        macros = [
            {
                "id": 3,
                "nome": "Learning",
                "descrizione": "Session",
                "system_key": "general_click_elements_learning",
                "system_payload": {"scope": "test"},
                "data_creazione": "2026-05-29 10:02:00",
                "data_ultima_modifica": "2026-05-29 10:03:00",
            }
        ]
        events = [
            {
                "time": 1,
                "type": "mouse",
                "event": "down",
                "x": 100,
                "y": 200,
                "normalized_x": 0.1,
                "normalized_y": 0.2,
                "game_element_id": 7,
                "ui_graph_id": "graph",
                "ui_node_id": "node",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("services.shared_knowledge_export_service.get_all_game_elements", return_value=[element]),
                patch("services.shared_knowledge_export_service.get_game_element_by_id", return_value=full_element),
                patch("services.shared_knowledge_export_service.get_all_macros", return_value=macros),
                patch("services.shared_knowledge_export_service.load_macro_events", return_value=events),
                patch("services.shared_knowledge_export_service.suggest_repeated_learning_patterns", return_value=[]),
            ):
                summary = export_shared_knowledge(Path(temp_dir))

            self.assertEqual(summary["game_elements"], 1)
            manifest = json.loads((Path(temp_dir) / "game_elements_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["game_elements"][0]["id"], 7)
            self.assertTrue((Path(temp_dir) / manifest["game_elements"][0]["image_path"]).exists())
            sessions = json.loads((Path(temp_dir) / "learning_sessions.json").read_text(encoding="utf-8"))
            self.assertEqual(sessions["learning_sessions"][0]["click_sequence"][0]["game_element_id"], 7)


if __name__ == "__main__":
    unittest.main()
