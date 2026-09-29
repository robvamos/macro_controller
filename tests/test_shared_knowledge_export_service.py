import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from game_elements import image_to_blob
from services.shared_knowledge_export_service import (
    _merge_game_elements,
    _merge_hero_observations,
    _normalize_existing_game_elements,
    _portable_element_name,
    _remap_session_element_ids,
    _build_shared_pattern_suggestions,
    _sanitize_portable,
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
                patch("services.shared_knowledge_export_service.RECOVERED_LEARNING_SESSIONS_DIR", Path(temp_dir) / "recovered"),
                patch("services.shared_knowledge_export_service.DOOMSDAY_LOCAL_DIR", Path(temp_dir) / "local"),
            ):
                summary = export_shared_knowledge(Path(temp_dir))

            self.assertEqual(summary["game_elements"], 1)
            manifest = json.loads((Path(temp_dir) / "game_elements_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["game_elements"][0]["id"], 7)
            self.assertTrue((Path(temp_dir) / manifest["game_elements"][0]["image_path"]).exists())
            sessions = json.loads((Path(temp_dir) / "learning_sessions.json").read_text(encoding="utf-8"))
            self.assertEqual(sessions["learning_sessions"][0]["click_sequence"][0]["game_element_id"], 7)
            self.assertNotIn("x", sessions["learning_sessions"][0]["click_sequence"][0])

    def test_export_adds_remote_and_local_knowledge_without_collisions_or_local_paths(self):
        image_blob = image_to_blob(Image.new("RGB", (12, 8), "blue"))
        first = {
            "id": 7,
            "nome": "Popup Close",
            "descrizione": "Locally improved description",
            "formato_immagine": "PNG",
            "data_creazione": "2026-05-29 10:00:00",
            "data_ultima_modifica": "2026-05-29 10:01:00",
        }
        second = {**first, "id": 8, "nome": "New Control"}
        full = [{**first, "immagine": image_blob}, {**second, "immagine": image_blob}]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "game_elements").mkdir()
            (root / "game_elements" / "shared.png").write_bytes(image_blob)
            (root / "game_elements_manifest.json").write_text(
                json.dumps(
                    {
                        "game_elements": [
                            {
                                "id": 7,
                                "name": "Popup Close",
                                "description": "Description learned elsewhere",
                                "image_path": "game_elements/shared.png",
                                "image_size": {"width": 12, "height": 8},
                                "computer_name": "OTHER-PC",
                                "source_path": "C:/Users/alice/capture.png",
                            },
                            {"id": 8, "name": "Remote Control", "description": "Keep this"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (root / "learning_sessions.json").write_text(
                json.dumps(
                    {
                        "learning_sessions": [
                            {
                                "name": "Local user session",
                                "system_key": "general_click_elements_learning",
                                "macro_id": 918,
                                "host_name": "OTHER-PC",
                                "created_at": "2026-01-01",
                                "click_sequence": [{"game_element_id": 8, "x": 111, "y": 222}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (root / "ui_semantic_graph.json").write_text(
                json.dumps(
                    {
                        "schema": "doomsday.ui_semantic_graph.v1",
                        "nodes": [{"node_id": "remote_node", "label": "Learned elsewhere"}],
                        "edges": [],
                    }
                ),
                encoding="utf-8",
            )
            macros = [
                {
                    "id": 9,
                    "nome": "local private machine name",
                    "descrizione": "Shared lesson",
                    "system_key": "general_click_elements_learning",
                    "system_payload": {"shortcut_path": "C:/Users/me/game.lnk", "scope": "startup"},
                    "data_creazione": "2026-02-02",
                    "data_ultima_modifica": "2026-02-03",
                }
            ]
            events = [
                {
                    "time": 1,
                    "type": "mouse",
                    "event": "down",
                    "x": 400,
                    "y": 300,
                    "normalized_x": 0.4,
                    "normalized_y": 0.3,
                    "game_element_id": 8,
                }
            ]
            with (
                patch("services.shared_knowledge_export_service.get_all_game_elements", return_value=[first, second]),
                patch(
                    "services.shared_knowledge_export_service.get_game_element_by_id",
                    side_effect=lambda element_id: next(item for item in full if item["id"] == element_id),
                ),
                patch("services.shared_knowledge_export_service.get_all_macros", return_value=macros),
                patch("services.shared_knowledge_export_service.load_macro_events", return_value=events),
                patch("services.shared_knowledge_export_service.RECOVERED_LEARNING_SESSIONS_DIR", root / "recovered"),
                patch("services.shared_knowledge_export_service.DOOMSDAY_LOCAL_DIR", root / "local"),
            ):
                export_shared_knowledge(root)

            manifest = json.loads((root / "game_elements_manifest.json").read_text(encoding="utf-8"))
            by_name = {item["name"]: item for item in manifest["game_elements"]}
            self.assertEqual(by_name["Popup Close"]["id"], 7)
            self.assertIn("Description learned elsewhere", by_name["Popup Close"]["description"])
            self.assertIn("Locally improved description", by_name["Popup Close"]["description"])
            self.assertEqual(by_name["New Control"]["id"], 9)
            self.assertNotIn("computer_name", json.dumps(manifest))
            self.assertNotIn("C:/Users", json.dumps(manifest))

            sessions = json.loads((root / "learning_sessions.json").read_text(encoding="utf-8"))[
                "learning_sessions"
            ]
            self.assertEqual(len(sessions), 2)
            incoming = next(item for item in sessions if item["created_at"] == "2026-02-02")
            self.assertEqual(incoming["name"], "general_click_elements_learning")
            self.assertNotIn("macro_id", incoming)
            self.assertNotIn("shortcut_path", json.dumps(incoming))
            self.assertNotIn('"x":', json.dumps(incoming))
            self.assertEqual(incoming["click_sequence"][0]["game_element_id"], 9)

            graph = json.loads((root / "ui_semantic_graph.json").read_text(encoding="utf-8"))
            self.assertIn("remote_node", {node["node_id"] for node in graph["nodes"]})

    def test_merge_game_elements_keeps_existing_ids_and_adds_conflicting_names_safely(self):
        merged, mapping = _merge_game_elements(
            [
                {"id": 3, "name": "Shared", "description": "Other workstation"},
                {"id": 4, "name": "Remote", "description": "Keep ID"},
            ],
            [
                {"id": 3, "name": " shared ", "description": "Local detail"},
                {"id": 4, "name": "Different", "description": "New element"},
            ],
        )
        self.assertEqual([item["id"] for item in merged], [3, 4, 5])
        self.assertEqual(mapping, {3: 3, 4: 5})
        self.assertIn("Other workstation", merged[0]["description"])
        self.assertIn("Local detail", merged[0]["description"])

    def test_private_capture_names_become_pixel_stable_and_duplicate_ids_remap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_dir = root / "game_elements"
            image_dir.mkdir()
            old_image = image_dir / "0003_recorded_click_locale_host_900x400.png"
            Image.new("RGB", (12, 8), "red").save(old_image)
            source_records = [
                {
                    "id": element_id,
                    "name": f"recorded_click_locale_host_{element_id}",
                    "image_path": f"game_elements/{old_image.name}",
                }
                for element_id in (3, 4)
            ]

            normalized, id_map = _normalize_existing_game_elements(source_records, root, image_dir)

            self.assertEqual(len(normalized), 1)
            self.assertEqual(normalized[0]["name"], _portable_element_name(source_records[0]["name"], normalized[0]["image_hash"]))
            self.assertTrue(normalized[0]["name"].startswith("observed_click_"))
            self.assertEqual(id_map, {3: 3, 4: 3})
            self.assertNotIn("locale", normalized[0]["image_path"])
            self.assertTrue((root / normalized[0]["image_path"]).is_file())

    def test_session_ids_remap_to_shared_ids_and_unknown_local_ids_are_cleared(self):
        session = {
            "system_key": "learning",
            "system_payload": {"recorded_click_element_ids": [11, 999]},
            "click_sequence": [
                {"game_element_id": 11, "previous_game_element_id": 999},
                {"game_element_id": 888, "previous_game_element_id": None},
            ],
        }

        portable = _remap_session_element_ids(session, {11: 2}, preserve_unknown=False, known_ids={2})

        self.assertEqual(portable["click_sequence"][0]["game_element_id"], 2)
        self.assertIsNone(portable["click_sequence"][0]["previous_game_element_id"])
        self.assertIsNone(portable["click_sequence"][1]["game_element_id"])
        self.assertEqual(portable["system_payload"]["recorded_click_element_ids"], [2])

    def test_legacy_shared_session_ids_follow_deduplicated_asset_ids(self):
        session = {"system_key": "learning", "click_sequence": [{"game_element_id": 4}]}

        portable = _remap_session_element_ids(session, {4: 3}, preserve_unknown=True, known_ids={3})

        self.assertEqual(portable["click_sequence"][0]["game_element_id"], 3)

    def test_sanitize_portable_removes_machine_paths_and_screen_coordinates(self):
        clean = _sanitize_portable(
            {
                "computer_name": "MACHINE",
                "shortcut_path": "C:/Users/me/game.lnk",
                "click_sequence": [{"x": 1234, "y": 567, "normalized_x": 0.2}],
            }
        )
        self.assertEqual(clean, {"click_sequence": [{"normalized_x": 0.2}]})

    def test_hero_observation_export_removes_machine_paths_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local = root / "local"
            shared = root / "shared"
            local.mkdir()
            (local / "20260929_100000.json").write_text(
                json.dumps(
                    {
                        "schema": "doomsday.hero_learning_observations.v1",
                        "session_name": "Hero inspection - Locale HOST\\user - 20260929_100000",
                        "observations": [
                            {
                                "frame_path": "C:/Users/user/private/frame.png",
                                "frame_sha256": "safe-digest",
                                "game_element_id": 7,
                                "ocr": {"text": "Hero screen"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(_merge_hero_observations(local, shared, {7: 70}, known_ids={70}), 1)
            published = shared / "20260929_100000.json"
            payload = json.loads(published.read_text(encoding="utf-8"))
            serialized = json.dumps(payload)
            self.assertNotIn("C:/Users", serialized)
            self.assertNotIn("HOST", serialized)
            self.assertNotIn("frame_path", serialized)
            self.assertEqual(payload["observations"][0]["frame_sha256"], "safe-digest")
            self.assertEqual(payload["observations"][0]["game_element_id"], 70)
            self.assertEqual(_merge_hero_observations(local, shared, {7: 70}, known_ids={70}), 1)

    def test_pattern_suggestions_require_distinct_portable_sessions(self):
        elements = [{"id": 7, "name": "Open"}, {"id": 8, "name": "Confirm"}]
        one_session = {
            "system_key": "learning",
            "created_at": "2026-01-01",
            "click_sequence": [{"game_element_id": 7}, {"game_element_id": 8}],
        }
        self.assertEqual(_build_shared_pattern_suggestions([one_session], elements), [])

        suggestions = _build_shared_pattern_suggestions(
            [one_session, {**one_session, "created_at": "2026-01-02"}], elements
        )
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["element_names"], ["Open", "Confirm"])
        self.assertEqual(suggestions[0]["source_session_count"], 2)


if __name__ == "__main__":
    unittest.main()
