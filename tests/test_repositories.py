import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repositories import backup_repository, database, game_element_repository, macro_repository, task_repository
from repositories import ui_graph_macro_link_repository
from services.system_macro_service import (
    ensure_launch_game_system_macro,
    remember_local_workstation_context,
    save_launch_game_local_variant,
)
from services.ui_graph_macro_link_service import get_macro_plan_for_ui_node, link_macro_to_ui_node


def sample_events(prefix="base"):
    return [
        {
            "time": 0,
            "type": "keyboard",
            "event": "press",
            "name": f"{prefix}_a",
            "button": "",
            "x": None,
            "y": None,
            "delta": 0,
            "is_pressed": True,
            "normalized_x": None,
            "normalized_y": None,
        },
        {
            "time": 150,
            "type": "mouse",
            "event": "move",
            "name": "",
            "button": "left",
            "x": 100.0,
            "y": 200.0,
            "delta": 0,
            "is_pressed": False,
            "normalized_x": 0.25,
            "normalized_y": 0.75,
        },
    ]


class RepositoryTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.db_path = self.base / "test_macro.db"
        self.legacy_db_path = self.base / "legacy_macro.db"

        self.patches = [
            patch.object(database, "DB_PATH", self.db_path),
            patch.object(database, "LEGACY_DB_PATH", self.legacy_db_path),
            patch.object(database, "ensure_project_directories", self._ensure_dirs),
        ]
        for active_patch in self.patches:
            active_patch.start()

        self._ensure_dirs()
        database.setup_main_table()
        database.setup_backup_table()
        database.setup_scheduled_tasks_table()
        database.setup_task_macro_sequence_table()
        database.setup_game_elements_table()
        database.setup_ui_graph_macro_links_table()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.tempdir.cleanup()

    def _ensure_dirs(self):
        self.base.mkdir(parents=True, exist_ok=True)

    def create_macro(self, name="MacroTest", events=None):
        events = events or sample_events()
        return macro_repository.salva_macro_test(
            name,
            "descrizione",
            10,
            "game.exe",
            events,
        )


class MacroRepositoryTests(RepositoryTestCase):
    def test_macro_save_load_duplicate_and_delete(self):
        macro_id = self.create_macro()

        metadata = macro_repository.get_macro_metadata_by_id(macro_id)
        all_macros = macro_repository.get_all_macros()
        loaded_events = macro_repository.load_macro_events(macro_id)

        self.assertEqual(metadata["nome"], "MacroTest")
        self.assertEqual(len(all_macros), 1)
        self.assertEqual(len(loaded_events), 2)

        duplicate_id, duplicate_name = macro_repository.duplicate_macro(macro_id)
        duplicate_events = macro_repository.load_macro_events(duplicate_id)

        self.assertNotEqual(duplicate_id, macro_id)
        self.assertNotEqual(duplicate_name, "MacroTest")
        self.assertEqual(duplicate_events, loaded_events)

        macro_repository.delete_macro("MacroTest")
        self.assertIsNone(macro_repository.get_macro_metadata_by_name("MacroTest"))

    def test_macro_events_preserve_recorded_click_element_graph_metadata(self):
        events = [
            {
                "time": 42,
                "type": "mouse",
                "event": "down",
                "button": "left",
                "normalized_x": 0.25,
                "normalized_y": 0.75,
                "game_element_id": 12,
                "previous_game_element_id": 11,
                "ui_graph_id": "doomsday-default-ui-graph",
                "ui_node_id": "shelter_interior_view",
            }
        ]

        macro_id = self.create_macro(events=events)
        loaded_events = macro_repository.load_macro_events(macro_id)

        self.assertEqual(loaded_events[0]["game_element_id"], 12)
        self.assertEqual(loaded_events[0]["previous_game_element_id"], 11)
        self.assertEqual(loaded_events[0]["ui_graph_id"], "doomsday-default-ui-graph")
        self.assertEqual(loaded_events[0]["ui_node_id"], "shelter_interior_view")

        references = macro_repository.get_game_element_event_references(12)
        self.assertEqual(sum(item["count"] for item in references), 1)

    def test_update_events_creates_backup_and_restore_works(self):
        macro_id = self.create_macro(events=sample_events("original"))
        original_events = macro_repository.load_macro_events(macro_id)

        updated_events = sample_events("updated")
        macro_repository.update_macro_events_only(macro_id, updated_events)

        backups = backup_repository.get_all_backups()
        self.assertEqual(len(backups), 1)
        self.assertEqual(macro_repository.load_macro_events(macro_id), updated_events)

        backup_repository.restore_macro_from_backup(backups[0]["id"])
        restored_events = macro_repository.load_macro_events(macro_id)
        self.assertEqual(restored_events, original_events)

    def test_protected_system_macro_cannot_be_deleted_and_duplicate_is_unprotected(self):
        system_macro_id = macro_repository.salva_macro_test(
            "Sistema · Avvia Test",
            "macro di sistema",
            1,
            "game.exe",
            [],
            macro_kind=macro_repository.SYSTEM_MACRO_KIND,
            is_protected=True,
            system_key="launch_game",
            system_payload={"shortcut_path": "C:/test.lnk", "target_exe": "game.exe"},
        )

        with self.assertRaises(ValueError):
            macro_repository.delete_macro("Sistema · Avvia Test")

        duplicate_id, _duplicate_name = macro_repository.duplicate_macro(system_macro_id)
        duplicate_metadata = macro_repository.get_macro_metadata_by_id(duplicate_id)
        self.assertEqual(duplicate_metadata["macro_kind"], macro_repository.SYSTEM_MACRO_KIND)
        self.assertFalse(duplicate_metadata["is_protected"])

    def test_ensure_launch_game_system_macro_creates_protected_entry(self):
        with patch("services.system_macro_service.load_app_config", return_value={
            "system_macros": {
                "launch_game": {
                    "shortcut_path": "C:/Users/Public/Desktop/Doomsday.lnk",
                    "target_exe": "Doomsday.exe",
                }
            }
        }):
            macro_id = ensure_launch_game_system_macro()

        metadata = macro_repository.get_macro_metadata_by_id(macro_id)
        self.assertEqual(metadata["macro_kind"], macro_repository.SYSTEM_MACRO_KIND)
        self.assertTrue(metadata["is_protected"])
        self.assertEqual(metadata["system_key"], "launch_game")
        self.assertEqual(metadata["system_payload"]["target_exe"], "Doomsday.exe")

    def test_save_launch_game_local_variant_creates_and_updates_per_workstation(self):
        with patch("services.system_macro_service.load_app_config", return_value={
            "system_macros": {
                "launch_game": {
                    "shortcut_path": "C:/Users/Public/Desktop/Doomsday.lnk",
                    "target_exe": "Doomsday.exe",
                }
            }
        }):
            ensure_launch_game_system_macro()

            with patch("services.system_macro_service.get_local_launch_context", return_value={
                "host_name": "TESTPC",
                "user_name": "Rob",
            }):
                macro_id, macro_name, created = save_launch_game_local_variant("D:/Custom/Doomsday.lnk")
                metadata = macro_repository.get_macro_metadata_by_id(macro_id)
                self.assertTrue(created)
                self.assertEqual(metadata["system_payload"]["shortcut_path"], "D:/Custom/Doomsday.lnk")
                self.assertEqual(metadata["system_payload"]["variant_scope"], "local_workstation")
                self.assertEqual(macro_name, "Sistema · Avvia Doomsday · Locale TESTPC\\Rob")
                self.assertFalse(metadata["is_protected"])

                updated_id, _updated_name, created_again = save_launch_game_local_variant("E:/Games/Doomsday.lnk")
                updated_metadata = macro_repository.get_macro_metadata_by_id(updated_id)
                self.assertEqual(updated_id, macro_id)
                self.assertFalse(created_again)
                self.assertEqual(updated_metadata["system_payload"]["shortcut_path"], "E:/Games/Doomsday.lnk")

    def test_remember_local_workstation_context_persists_startup_identity(self):
        saved = {}

        with (
            patch("services.system_macro_service.load_app_config", return_value={}),
            patch("services.system_macro_service.save_app_config", side_effect=lambda config: saved.update(config)),
            patch("services.system_macro_service.get_local_launch_context", return_value={
                "host_name": "TESTPC",
                "user_name": "Rob",
            }),
        ):
            context = remember_local_workstation_context()

        self.assertEqual(context["host_name"], "TESTPC")
        self.assertEqual(saved["local_workstation"]["host_name"], "TESTPC")
        self.assertEqual(saved["local_workstation"]["user_name"], "Rob")
        self.assertIn("last_seen_at", saved["local_workstation"])


class TaskRepositoryTests(RepositoryTestCase):
    def test_scheduled_task_crud_and_sequence(self):
        macro_id = self.create_macro()

        task_id = task_repository.create_scheduled_task(
            nome="TaskTest",
            descrizione="desc",
            macro_id=macro_id,
            schedulazione_tipo="intervallo",
            intervallo_ore=1,
            intervallo_minuti=30,
        )

        task = task_repository.get_scheduled_task_by_id(task_id)
        self.assertEqual(task["nome"], "TaskTest")
        self.assertEqual(task["macro_id"], macro_id)
        self.assertEqual(task["schedulazione_tipo"], "intervallo")

        seq1 = task_repository.add_macro_to_task_sequence(task_id, macro_id, attesa_secondi=5)
        sequence = task_repository.get_task_macro_sequence(task_id)
        self.assertEqual(len(sequence), 1)
        self.assertEqual(sequence[0]["attesa_secondi"], 5)

        task_repository.update_macro_sequence_wait_time(seq1, 9)
        sequence = task_repository.get_task_macro_sequence(task_id)
        self.assertEqual(sequence[0]["attesa_secondi"], 9)

        task_repository.start_task_scheduling(task_id)
        task_repository.increment_task_execution_count(task_id)
        task_repository.stop_task_scheduling(task_id)

        task = task_repository.get_scheduled_task_by_id(task_id)
        self.assertEqual(task["stato"], "stopped")

        task_repository.remove_macro_from_task_sequence(seq1)
        self.assertEqual(task_repository.get_task_macro_sequence(task_id), [])

        task_repository.delete_scheduled_task(task_id)
        self.assertIsNone(task_repository.get_scheduled_task_by_id(task_id))

    def test_task_completion_and_reactivation(self):
        macro_id = self.create_macro()
        task_id = task_repository.create_scheduled_task(
            nome="TaskComplete",
            descrizione="desc",
            macro_id=macro_id,
            schedulazione_tipo="intervallo",
            intervallo_ore=0,
            intervallo_minuti=1,
            terminazione_tipo="esecuzioni",
            terminazione_valore=1,
        )

        task_repository.start_task_scheduling(task_id)
        task_repository.increment_task_execution_count(task_id)

        completed = task_repository.check_and_complete_task_if_needed(task_id)
        task = task_repository.get_scheduled_task_by_id(task_id)

        self.assertTrue(completed)
        self.assertEqual(task["stato"], "completed")
        self.assertFalse(task["attivo"])

        task_repository.reactivate_completed_task(task_id)
        task = task_repository.get_scheduled_task_by_id(task_id)
        self.assertEqual(task["stato"], "stopped")
        self.assertTrue(task["attivo"])
        self.assertEqual(task["conteggio_esecuzioni"], 0)


class GameElementRepositoryTests(RepositoryTestCase):
    def test_game_element_crud(self):
        element_id = game_element_repository.create_game_element(
            "Elemento1",
            "desc",
            b"binary-image",
            "png",
        )

        element = game_element_repository.get_game_element_by_id(element_id)
        self.assertEqual(element["nome"], "Elemento1")
        self.assertEqual(element["immagine"], b"binary-image")

        game_element_repository.update_game_element(
            element_id,
            nome="Elemento2",
            descrizione="updated",
            immagine_blob=b"new-image",
            formato_immagine="jpg",
        )
        updated = game_element_repository.get_game_element_by_id(element_id)
        self.assertEqual(updated["nome"], "Elemento2")
        self.assertEqual(updated["formato_immagine"], "jpg")

        all_elements = game_element_repository.get_all_game_elements()
        self.assertEqual(len(all_elements), 1)

        game_element_repository.delete_game_element(element_id)
        self.assertIsNone(game_element_repository.get_game_element_by_id(element_id))


class UIGraphMacroLinkRepositoryTests(RepositoryTestCase):
    def test_ui_graph_macro_link_repository_and_service_produce_macro_plan(self):
        macro_id = self.create_macro(name="EntraNelRifugio")

        link_id = link_macro_to_ui_node(
            graph_id="doomsday-default-ui-graph",
            node_id="playable_interface_without_boot_popup",
            macro_id=macro_id,
            intent_key="enter_shelter",
            relation_type="preferred",
            priority=10,
            notes="Macro primaria per entrare nel rifugio.",
        )

        links = ui_graph_macro_link_repository.get_ui_graph_macro_links(
            graph_id="doomsday-default-ui-graph",
            node_id="playable_interface_without_boot_popup",
            intent_key="enter_shelter",
        )
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["id"], link_id)
        self.assertEqual(links[0]["relation_type"], "preferred")

        plan = get_macro_plan_for_ui_node(
            graph_id="doomsday-default-ui-graph",
            node_id="playable_interface_without_boot_popup",
            intent_key="enter_shelter",
        )
        self.assertEqual(plan.target_node_id, "playable_interface_without_boot_popup")
        self.assertEqual(len(plan.candidate_links), 1)
        self.assertEqual(plan.candidate_links[0].macro_name, "EntraNelRifugio")


if __name__ == "__main__":
    unittest.main()
