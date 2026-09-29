import unittest
from unittest.mock import Mock, patch

from services import system_macro_service


class SystemMacroServiceTests(unittest.TestCase):
    def test_run_system_macro_skips_launch_when_process_is_running(self):
        metadata = {
            "system_key": "launch_game",
            "eseguibile": "Doomsday.exe",
            "system_payload": {
                "shortcut_path": "D:/Test/Doomsday.lnk",
                "target_exe": "Doomsday.exe",
            },
        }
        log_callback = Mock()

        with (
            patch.object(system_macro_service, "is_process_running", return_value=True),
            patch.object(system_macro_service, "wait_for_game_fullscreen", return_value={
                "launched": False,
                "already_running": True,
                "fullscreen_ready": True,
                "fallback_required": False,
                "game_interface_ready": False,
                "next_step": "wait_for_initial_blocking_popup",
                "blocking_popups_pending": True,
            }) as wait_mock,
            patch.object(system_macro_service, "wait_for_initial_blocking_popup", return_value={
                "launched": False,
                "already_running": True,
                "fullscreen_ready": True,
                "fallback_required": False,
                "game_interface_ready": False,
                "next_step": "dismiss_initial_blocking_popup",
                "blocking_popups_pending": True,
                "blocking_popup_detected": True,
            }) as popup_wait_mock,
        ):
            result = system_macro_service.run_system_macro(metadata, log_callback)

        self.assertFalse(result["launched"])
        self.assertTrue(result["already_running"])
        self.assertTrue(result["fullscreen_ready"])
        self.assertFalse(result["game_interface_ready"])
        self.assertEqual(result["next_step"], "dismiss_initial_blocking_popup")
        wait_mock.assert_called_once()
        popup_wait_mock.assert_called_once()

    def test_run_system_macro_launches_shortcut_when_process_is_missing(self):
        metadata = {
            "system_key": "launch_game",
            "eseguibile": "Doomsday.exe",
            "system_payload": {
                "shortcut_path": "D:/Test/Doomsday.lnk",
                "target_exe": "Doomsday.exe",
            },
        }
        log_callback = Mock()

        with (
            patch.object(system_macro_service, "is_process_running", return_value=False),
            patch.object(system_macro_service, "get_local_launch_game_variant_for_current_context", return_value=None),
            patch("services.system_macro_service.os.path.exists", return_value=True),
            patch("services.system_macro_service.os.startfile") as startfile_mock,
            patch.object(system_macro_service, "wait_for_game_fullscreen", return_value={
                "launched": True,
                "already_running": False,
                "fullscreen_ready": True,
                "fallback_required": False,
                "game_interface_ready": False,
                "next_step": "wait_for_initial_blocking_popup",
                "blocking_popups_pending": True,
            }) as wait_mock,
            patch.object(system_macro_service, "wait_for_initial_blocking_popup", return_value={
                "launched": True,
                "already_running": False,
                "fullscreen_ready": True,
                "fallback_required": False,
                "game_interface_ready": False,
                "next_step": "dismiss_initial_blocking_popup",
                "blocking_popups_pending": True,
                "blocking_popup_detected": True,
            }) as popup_wait_mock,
        ):
            result = system_macro_service.run_system_macro(metadata, log_callback)

        startfile_mock.assert_called_once_with("D:/Test/Doomsday.lnk")
        self.assertTrue(result["launched"])
        self.assertFalse(result["already_running"])
        self.assertTrue(result["fullscreen_ready"])
        self.assertFalse(result["game_interface_ready"])
        self.assertEqual(result["next_step"], "dismiss_initial_blocking_popup")
        wait_mock.assert_called_once()
        popup_wait_mock.assert_called_once()

    def test_run_system_macro_prefers_db_local_variant_for_current_workstation(self):
        metadata = {
            "system_key": "launch_game",
            "eseguibile": "Doomsday.exe",
            "system_payload": {
                "shortcut_path": "D:/Test/Doomsday.lnk",
                "target_exe": "Doomsday.exe",
            },
        }
        local_variant = {
            "system_key": "launch_game",
            "eseguibile": "Doomsday.exe",
            "system_payload": {
                "shortcut_path": "D:/Custom/StationDoomsday.lnk",
                "target_exe": "Doomsday.exe",
                "variant_scope": "local_workstation",
                "host_name": "TESTPC",
                "user_name": "Rob",
            },
        }
        log_callback = Mock()

        with (
            patch.object(system_macro_service, "get_local_launch_game_variant_for_current_context", return_value=local_variant),
            patch.object(system_macro_service, "is_process_running", return_value=False),
            patch("services.system_macro_service.os.path.exists", return_value=True),
            patch("services.system_macro_service.os.startfile") as startfile_mock,
            patch.object(system_macro_service, "wait_for_game_fullscreen", return_value={
                "launched": True,
                "already_running": False,
                "fullscreen_ready": True,
                "fallback_required": False,
                "game_interface_ready": False,
                "next_step": "wait_for_initial_blocking_popup",
                "blocking_popups_pending": True,
            }),
            patch.object(system_macro_service, "wait_for_initial_blocking_popup", return_value={
                "launched": True,
                "already_running": False,
                "fullscreen_ready": True,
                "fallback_required": False,
                "game_interface_ready": False,
                "next_step": "dismiss_initial_blocking_popup",
                "blocking_popups_pending": True,
                "blocking_popup_detected": True,
            }),
        ):
            system_macro_service.run_system_macro(metadata, log_callback)

        startfile_mock.assert_called_once_with("D:/Custom/StationDoomsday.lnk")

    def test_wait_for_game_fullscreen_requires_fallback_after_timeout(self):
        log_callback = Mock()

        with (
            patch.object(system_macro_service, "is_process_fullscreen", return_value=False),
            patch("services.system_macro_service.time.sleep"),
            patch("services.system_macro_service.time.monotonic", side_effect=[0.0, 1.0, 2.0, 3.1]),
        ):
            result = system_macro_service.wait_for_game_fullscreen(
                "Doomsday.exe",
                poll_interval_sec=1,
                timeout_sec=3,
                log_callback=log_callback,
                launched_now=True,
            )

        self.assertFalse(result["fullscreen_ready"])
        self.assertTrue(result["fallback_required"])
        self.assertFalse(result["game_interface_ready"])
        self.assertEqual(result["next_step"], "fallback_required")

    def test_resolve_launch_shortcut_for_current_context_prefers_local_variant(self):
        local_variant = {
            "system_payload": {
                "shortcut_path": "D:/Custom/StationDoomsday.lnk",
                "variant_scope": "local_workstation",
            }
        }
        with patch.object(system_macro_service, "get_local_launch_game_variant_for_current_context", return_value=local_variant):
            result = system_macro_service.resolve_launch_shortcut_for_current_context()

        self.assertEqual(result, "D:/Custom/StationDoomsday.lnk")

    def test_launch_game_definition_exposes_full_interface_objective(self):
        definition = system_macro_service.get_launch_game_system_macro_definition()

        payload = definition["payload"]
        self.assertIn("interfaccia del gioco", payload["objective"])
        self.assertIn("dismiss_initial_blocking_popups", payload["workflow_stages"])
        self.assertEqual(payload["post_fullscreen_status"], "pending_game_loaded_check")
        self.assertEqual(payload["initial_popup_poll_interval_sec"], 10)
        self.assertEqual(payload["blocking_popup_element_name"], "popup_exit_close_symbol")

    def test_is_process_fullscreen_returns_true_when_rect_matches_monitor(self):
        with (
            patch.object(system_macro_service, "get_process_client_rect", return_value=(0, 0, 1920, 1080)),
            patch.object(system_macro_service, "get_monitor_rect_for_window", return_value=(0, 0, 1920, 1080)),
        ):
            self.assertTrue(system_macro_service.is_process_fullscreen("Doomsday.exe"))

    def test_wait_for_initial_blocking_popup_detects_popup_from_full_window(self):
        log_callback = Mock()
        base_result = {
            "launched": True,
            "already_running": False,
            "fullscreen_ready": True,
            "fallback_required": False,
            "game_interface_ready": False,
            "next_step": "wait_for_initial_blocking_popup",
            "blocking_popups_pending": True,
        }
        fake_match = Mock(score=0.93, center=(1200, 700))

        with (
            patch.object(system_macro_service, "get_process_client_rect", return_value=(0, 0, 1920, 1080)),
            patch.object(system_macro_service, "evaluate_ui_graph", return_value=Mock(
                graph_id="doomsday-default-ui-graph",
                active_node_ids=("initial_blocking_popup_close_symbol",),
                get_node_result=Mock(return_value=Mock(
                    active=True,
                    condition_results=(Mock(search_result=Mock(
                        found=True,
                        score=0.93,
                        center=(1200, 700),
                        matched_element_name="popup_exit_close_symbol",
                    )),),
                )),
            )) as match_mock,
        ):
            result = system_macro_service.wait_for_initial_blocking_popup(
                "Doomsday.exe",
                poll_interval_sec=10,
                element_name="popup_exit_close_symbol",
                match_threshold=0.85,
                log_callback=log_callback,
                base_result=base_result,
            )

        self.assertTrue(result["blocking_popup_detected"])
        self.assertEqual(result["next_step"], "dismiss_initial_blocking_popup")
        self.assertEqual(result["blocking_popup_center"], (1200, 700))
        self.assertEqual(result["ui_graph_id"], "doomsday-default-ui-graph")
        match_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
