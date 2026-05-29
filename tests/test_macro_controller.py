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
            patch.object(macro_controller, "_move_mouse_absolute"),
            patch.object(macro_controller, "_dispatch_mouse_button"),
            patch.object(macro_controller.keyboard, "press"),
        ):
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
        logged_messages = [call.args[0] for call in log_callback.call_args_list if call.args]
        self.assertTrue(any("Contesto visivo non compatibile all'avvio dell'iterazione" in message for message in logged_messages))


if __name__ == "__main__":
    unittest.main()
