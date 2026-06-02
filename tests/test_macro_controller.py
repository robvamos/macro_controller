import threading
import unittest
from unittest.mock import Mock, patch

import macro_controller


class MacroControllerRobustnessTests(unittest.TestCase):
    def tearDown(self):
        macro_controller._recording_active = False
        macro_controller._recording_thread = None
        macro_controller._recording_stop_event.clear()

    def test_wait_with_event_returns_true_when_signalled(self):
        stop_event = threading.Event()
        stop_event.set()
        self.assertTrue(macro_controller._wait_with_event(stop_event, 0.5))

    def test_stop_recording_signals_event_and_joins_real_thread(self):
        worker_finished = threading.Event()

        def worker():
            macro_controller._recording_thread = threading.current_thread()
            macro_controller._recording_stop_event.wait(1.0)
            worker_finished.set()

        thread = threading.Thread(target=worker, daemon=True, name="test-recording-thread")
        macro_controller._recording_active = True
        macro_controller._recording_thread = thread
        thread.start()

        with patch.object(macro_controller.keyboard, "unhook_all"), patch.object(macro_controller.mouse, "unhook_all"):
            stopped = macro_controller.stop_recording(log_callback=Mock())

        self.assertTrue(stopped)
        self.assertTrue(worker_finished.wait(timeout=1.0))
        self.assertTrue(macro_controller._recording_stop_event.is_set())

    def test_playback_emits_debug_for_executed_events(self):
        log_callback = Mock()
        events = [
            {"time": 0, "type": "mouse", "event": "down", "button": "left", "normalized_x": 0.5, "normalized_y": 0.25},
            {"time": 10, "type": "key", "event": "down", "name": "a"},
        ]

        with (
            patch.object(macro_controller, "get_foreground_process_name", return_value="Doomsday.exe"),
            patch.object(macro_controller, "get_game_window_rect", return_value=(100, 200, 300, 600)),
            patch.object(macro_controller, "_create_visual_click_guard") as create_guard,
            patch.object(macro_controller, "_move_mouse_absolute"),
            patch.object(macro_controller, "_dispatch_mouse_button"),
            patch.object(macro_controller.keyboard, "press"),
        ):
            fake_guard = Mock()
            fake_guard.verify_or_prime.return_value = {"ok": True, "primed": True, "score": 1.0, "threshold": 0.8}
            create_guard.return_value = fake_guard
            macro_controller.clear_playback_stop_request()
            macro_controller.play_macro_events(events, "Doomsday.exe", log_callback=log_callback)

        logged_messages = [call.args[0] for call in log_callback.call_args_list if call.args]
        self.assertTrue(any("DEBUG PLAYBACK [1/2] mouse_down" in message for message in logged_messages))
        self.assertTrue(any("DEBUG PLAYBACK [2/2] key_down" in message for message in logged_messages))

    def test_playback_stops_when_visual_click_context_is_not_compatible(self):
        log_callback = Mock()
        events = [
            {"time": 0, "type": "mouse", "event": "down", "button": "left", "normalized_x": 0.5, "normalized_y": 0.25},
            {"time": 10, "type": "mouse", "event": "down", "button": "left", "normalized_x": 0.6, "normalized_y": 0.35},
        ]
        fake_guard = Mock()
        fake_guard.verify_or_prime.side_effect = [
            {"ok": True, "primed": True, "score": 1.0, "threshold": 0.8},
            {"ok": False, "primed": False, "score": 0.21, "threshold": 0.8},
        ]

        with (
            patch.object(macro_controller, "get_foreground_process_name", return_value="Doomsday.exe"),
            patch.object(macro_controller, "get_game_window_rect", return_value=(100, 200, 300, 600)),
            patch.object(macro_controller, "_create_visual_click_guard", return_value=fake_guard),
            patch.object(macro_controller, "_attempt_popup_recovery", return_value=(False, None, None)) as recovery,
            patch.object(macro_controller, "_move_mouse_absolute"),
            patch.object(macro_controller, "_dispatch_mouse_button"),
        ):
            macro_controller.clear_playback_stop_request()
            macro_controller.play_macro_events(
                events,
                "Doomsday.exe",
                log_callback=log_callback,
                loop_enabled=True,
                loop_delay=0,
                max_repetitions=2,
            )

        self.assertEqual(fake_guard.verify_or_prime.call_count, 2)
        recovery.assert_called_once()
        logged_messages = [call.args[0] for call in log_callback.call_args_list if call.args]
        self.assertTrue(any("Contesto visivo non compatibile all'avvio dell'iterazione" in message for message in logged_messages))
        self.assertTrue(any("tentativo di recovery non ha ripristinato il riferimento" in message for message in logged_messages))

    def test_playback_recovers_from_visual_mismatch_and_continues_when_popup_recovery_succeeds(self):
        log_callback = Mock()
        events = [
            {"time": 0, "type": "mouse", "event": "down", "button": "left", "normalized_x": 0.5, "normalized_y": 0.25},
        ]
        fake_guard = Mock()
        fake_guard.verify_or_prime.side_effect = [
            {"ok": True, "primed": True, "score": 1.0, "threshold": 0.8},
            {"ok": False, "primed": False, "score": 0.42, "threshold": 0.8},
        ]

        with (
            patch.object(macro_controller, "get_foreground_process_name", return_value="Doomsday.exe"),
            patch.object(macro_controller, "get_game_window_rect", return_value=(100, 200, 300, 600)),
            patch.object(macro_controller, "_create_visual_click_guard", return_value=fake_guard),
            patch.object(
                macro_controller,
                "_attempt_popup_recovery",
                return_value=(True, "back_return_symbol", {"ok": True, "primed": False, "score": 0.91, "threshold": 0.8}),
            ) as recovery,
            patch.object(macro_controller, "_move_mouse_absolute"),
            patch.object(macro_controller, "_dispatch_mouse_button") as dispatch_button,
        ):
            macro_controller.clear_playback_stop_request()
            macro_controller.play_macro_events(
                events,
                "Doomsday.exe",
                log_callback=log_callback,
                loop_enabled=True,
                loop_delay=0,
                max_repetitions=2,
            )

        recovery.assert_called_once()
        self.assertEqual(dispatch_button.call_count, 2)
        logged_messages = [call.args[0] for call in log_callback.call_args_list if call.args]
        self.assertTrue(any("visual_guard_recovered strategy='back_return_symbol'" in message for message in logged_messages))

    def test_playback_primes_fixed_visual_reference_from_recorded_element(self):
        log_callback = Mock()
        events = [
            {
                "time": 0,
                "type": "mouse",
                "event": "down",
                "button": "left",
                "normalized_x": 0.5,
                "normalized_y": 0.25,
                "game_element_id": 12,
            },
        ]
        fake_guard = Mock()
        fake_guard.verify_or_prime.return_value = {"ok": True, "primed": False, "score": 1.0, "threshold": 0.8}

        with (
            patch.object(macro_controller, "get_foreground_process_name", return_value="Doomsday.exe"),
            patch.object(macro_controller, "get_game_window_rect", return_value=(100, 200, 300, 600)),
            patch.object(macro_controller, "_create_visual_click_guard", return_value=fake_guard),
            patch.object(macro_controller, "_move_mouse_absolute"),
            patch.object(macro_controller, "_dispatch_mouse_button"),
            patch.object(macro_controller, "get_game_element_by_id", return_value={"id": 12, "nome": "ref", "immagine": b"blob", "formato_immagine": "PNG"}),
            patch.object(macro_controller, "blob_to_image", return_value=Mock(copy=Mock(return_value=Mock()), close=Mock())),
        ):
            macro_controller.clear_playback_stop_request()
            macro_controller.play_macro_events(events, "Doomsday.exe", log_callback=log_callback)

        fake_guard.set_reference_image.assert_called_once()

    def test_playback_loop_freezes_runtime_reference_after_first_prime(self):
        log_callback = Mock()
        events = [
            {"time": 0, "type": "mouse", "event": "down", "button": "left", "normalized_x": 0.5, "normalized_y": 0.25},
        ]
        fake_guard = Mock()
        fake_guard.verify_or_prime.return_value = {"ok": True, "primed": True, "score": 1.0, "threshold": 0.8}
        fake_guard.has_reference.return_value = False

        with (
            patch.object(macro_controller, "get_foreground_process_name", return_value="Doomsday.exe"),
            patch.object(macro_controller, "get_game_window_rect", return_value=(100, 200, 300, 600)),
            patch.object(macro_controller, "_create_visual_click_guard", return_value=fake_guard),
            patch.object(macro_controller, "_move_mouse_absolute"),
            patch.object(macro_controller, "_dispatch_mouse_button"),
            patch.object(macro_controller, "_prime_visual_guard_from_recorded_macro", return_value=False),
        ):
            macro_controller.clear_playback_stop_request()
            macro_controller.play_macro_events(
                events,
                "Doomsday.exe",
                log_callback=log_callback,
                loop_enabled=True,
                loop_delay=0,
                max_repetitions=1,
            )

        fake_guard.freeze_current_reference.assert_called_once()

    def test_popup_recovery_uses_close_symbol_when_available(self):
        fake_guard = Mock()
        fake_guard.verify_or_prime.return_value = {"ok": True, "primed": False, "score": 0.92, "threshold": 0.8}
        no_match = Mock(found=False, center=None, matched_element_name=None)
        search_result = Mock(found=True, center=(700, 400), matched_element_name="popup_exit_close_symbol")

        with (
            patch.object(macro_controller, "search_game_window_elements", side_effect=[no_match, search_result]),
            patch.object(macro_controller, "_left_click_at") as left_click,
        ):
            recovered, strategy, verify_result = macro_controller._attempt_popup_recovery(
                target_exe="Doomsday.exe",
                game_rect=(100, 100, 1100, 900),
                expected_abs_x=300,
                expected_abs_y=250,
                click_context_guard=fake_guard,
                log_callback=Mock(),
            )

        self.assertTrue(recovered)
        self.assertEqual(strategy, "close_symbol")
        self.assertEqual(verify_result["ok"], True)
        left_click.assert_called_once_with(700, 400)

    def test_popup_recovery_clicks_back_return_symbol_multiple_times_until_reference_is_back(self):
        fake_guard = Mock()
        fake_guard.verify_or_prime.side_effect = [
            {"ok": False, "primed": False, "score": 0.44, "threshold": 0.8},
            {"ok": True, "primed": False, "score": 0.90, "threshold": 0.8},
        ]
        back_return_match = Mock(found=True, center=(440, 160), matched_element_name="popup_back_return_symbol")

        with (
            patch.object(macro_controller, "search_game_window_elements", side_effect=[back_return_match, back_return_match]),
            patch.object(macro_controller, "_left_click_at") as left_click,
        ):
            recovered, strategy, verify_result = macro_controller._attempt_popup_recovery(
                target_exe="Doomsday.exe",
                game_rect=(100, 100, 1100, 900),
                expected_abs_x=300,
                expected_abs_y=250,
                click_context_guard=fake_guard,
                log_callback=Mock(),
            )

        self.assertTrue(recovered)
        self.assertEqual(strategy, "back_return_symbol")
        self.assertEqual(verify_result["ok"], True)
        self.assertEqual(left_click.call_count, 2)

    def test_popup_recovery_falls_back_to_empty_space_band(self):
        fake_guard = Mock()
        fake_guard.verify_or_prime.side_effect = [
            {"ok": False, "primed": False, "score": 0.30, "threshold": 0.8},
            {"ok": True, "primed": False, "score": 0.88, "threshold": 0.8},
        ]
        no_match = Mock(found=False, center=None, matched_element_name=None)

        with (
            patch.object(macro_controller, "search_game_window_elements", side_effect=[no_match, no_match]),
            patch.object(macro_controller, "_left_click_at") as left_click,
        ):
            recovered, strategy, verify_result = macro_controller._attempt_popup_recovery(
                target_exe="Doomsday.exe",
                game_rect=(100, 100, 1100, 900),
                expected_abs_x=300,
                expected_abs_y=250,
                click_context_guard=fake_guard,
                log_callback=Mock(),
            )

        self.assertTrue(recovered)
        self.assertEqual(strategy, "empty_space_band_4")
        self.assertEqual(verify_result["ok"], True)
        self.assertGreaterEqual(left_click.call_count, 2)

    def test_mouse_down_recording_captures_clicked_element_observation(self):
        observation = Mock(
            element_id=7,
            graph_id="doomsday-default-ui-graph",
            view_node_id="shelter_interior_view",
            element_name="recorded_click_test_000001ms_150x250",
        )
        log_callback = Mock()

        macro_controller._eventi_registrati = []
        macro_controller._recording_active = True
        macro_controller._target_process_name = "Doomsday.exe"
        macro_controller._recording_macro_name = "Test macro"
        macro_controller._recording_log_callback = log_callback
        macro_controller._recorded_click_element_count = 0

        event = macro_controller.mouse.ButtonEvent("down", "left", 1.0)
        with (
            patch.object(macro_controller, "get_game_window_rect", return_value=(100, 200, 300, 400)),
            patch.object(macro_controller.mouse, "get_position", return_value=(150, 250)),
            patch.object(macro_controller, "now", return_value=123),
            patch.object(macro_controller, "register_recorded_click_element", return_value=observation) as capture,
        ):
            macro_controller.mouse_hook(event)

        self.assertEqual(len(macro_controller._eventi_registrati), 1)
        recorded = macro_controller._eventi_registrati[0]
        self.assertEqual(recorded["game_element_id"], 7)
        self.assertEqual(recorded["ui_node_id"], "shelter_interior_view")
        self.assertEqual(macro_controller._recorded_click_element_count, 1)
        capture.assert_called_once()

    def test_recording_detects_ui_node_once_at_start_and_applies_to_events(self):
        log_callback = Mock()

        with (
            patch.object(macro_controller.psutil, "process_iter", return_value=[Mock(info={"name": "Doomsday.exe"})]),
            patch.object(macro_controller, "wait_for_app_window", return_value=True),
            patch.object(macro_controller, "get_foreground_process_name", return_value="Doomsday.exe"),
            patch.object(macro_controller, "get_game_window_rect", return_value=(100, 200, 500, 600)),
            patch.object(macro_controller, "classify_doomsday_view", return_value="exterior_region_view") as classify,
            patch.object(macro_controller.keyboard, "hook", side_effect=lambda callback: callback(Mock(event_type=macro_controller.keyboard.KEY_DOWN, name="a"))),
            patch.object(macro_controller.mouse, "hook"),
            patch.object(macro_controller.keyboard, "unhook_all"),
            patch.object(macro_controller.mouse, "unhook_all"),
        ):
            events = macro_controller.registra_eventi(
                nome_macro="Test vista",
                durata_sec=0.01,
                target_exe="Doomsday.exe",
                log_callback=log_callback,
            )

        classify.assert_called_once_with((100, 200, 500, 600))
        self.assertEqual(events[0]["ui_graph_id"], "doomsday-default-ui-graph")
        self.assertEqual(events[0]["ui_node_id"], "exterior_region_view")


if __name__ == "__main__":
    unittest.main()
