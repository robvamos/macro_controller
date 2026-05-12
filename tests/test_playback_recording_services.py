import unittest
from unittest.mock import Mock

from core.app_state import AppState
from services.operation_state_service import OperationStateService
from services.playback_service import PlaybackService
from services.recording_service import RecordingService


class PlaybackServiceTests(unittest.TestCase):
    def setUp(self):
        self.state = AppState()
        self.state_service = OperationStateService(self.state)
        self.service = PlaybackService(self.state, self.state_service)

    def test_start_playback_refuses_when_already_active(self):
        self.state.playing_flag = True
        self.assertFalse(self.service.start_playback(loop_enabled=True))

    def test_run_playback_handles_cancelled_target_wait(self):
        stop_focus = Mock()
        cancelled = Mock()
        failed = Mock()

        self.state.playing_flag = True
        self.service.run_playback(
            macro_events=[],
            target_exe="game.exe",
            loop_enabled=False,
            loop_delay=0,
            max_repetitions=None,
            gui_log=Mock(),
            event_callback=Mock(),
            wait_for_app_window=lambda *args, **kwargs: False,
            play_macro_events=Mock(),
            is_playback_stop_requested=lambda: True,
            start_focus_monitoring=Mock(),
            stop_focus_monitoring=stop_focus,
            on_target_wait_cancelled=cancelled,
            on_target_wait_failed=failed,
            on_before_playback=Mock(),
            on_playback_finished=Mock(),
        )

        self.assertFalse(self.state.playing_flag)
        stop_focus.assert_called_once()
        cancelled.assert_called_once()
        failed.assert_not_called()

    def test_run_playback_success_sets_target_and_finishes(self):
        play_macro_events = Mock()
        start_focus = Mock()
        stop_focus = Mock()
        before_playback = Mock()
        finished = Mock()

        self.state.playing_flag = True
        self.service.run_playback(
            macro_events=[{"time": 0}],
            target_exe="game.exe",
            loop_enabled=True,
            loop_delay=1.5,
            max_repetitions=3,
            gui_log=Mock(),
            event_callback=Mock(),
            wait_for_app_window=lambda *args, **kwargs: True,
            play_macro_events=play_macro_events,
            is_playback_stop_requested=lambda: False,
            start_focus_monitoring=start_focus,
            stop_focus_monitoring=stop_focus,
            on_target_wait_cancelled=Mock(),
            on_target_wait_failed=Mock(),
            on_before_playback=before_playback,
            on_playback_finished=finished,
        )

        start_focus.assert_called_once()
        before_playback.assert_called_once()
        play_macro_events.assert_called_once()
        finished.assert_called_once()
        stop_focus.assert_called_once()
        self.assertFalse(self.state.playing_flag)
        self.assertIsNone(self.state.current_target_exe)


class RecordingServiceTests(unittest.TestCase):
    def setUp(self):
        self.state = AppState()
        self.state_service = OperationStateService(self.state)
        self.service = RecordingService(self.state, self.state_service)

    def test_start_recording_session_sets_state(self):
        started = self.service.start_recording_session(target_exe="game.exe", duration_sec=7)
        self.assertTrue(started)
        self.assertTrue(self.state.recording_flag)
        self.assertEqual(self.state.current_target_exe, "game.exe")
        self.assertEqual(self.state.recording_duration, 7)

    def test_new_macro_recording_handles_empty_recording(self):
        empty = Mock()
        finished = Mock()

        self.state.recording_flag = True
        self.service.run_new_macro_recording(
            macro_name="macro",
            macro_desc="desc",
            macro_duration=5,
            macro_exe="game.exe",
            registra_eventi=lambda **kwargs: [],
            save_macro=Mock(),
            log_callback=Mock(),
            on_recording_started=Mock(),
            on_empty_recording=empty,
            on_save_error=Mock(),
            on_cancelled=Mock(),
            on_unhandled_error=Mock(),
            on_finished=finished,
        )

        empty.assert_called_once()
        finished.assert_called_once()
        self.assertFalse(self.state.recording_flag)

    def test_new_macro_recording_saves_events(self):
        save_macro = Mock()
        finished = Mock()

        self.state.recording_flag = True
        self.service.run_new_macro_recording(
            macro_name="macro",
            macro_desc="desc",
            macro_duration=5,
            macro_exe="game.exe",
            registra_eventi=lambda **kwargs: [{"time": 0}],
            save_macro=save_macro,
            log_callback=Mock(),
            on_recording_started=Mock(),
            on_empty_recording=Mock(),
            on_save_error=Mock(),
            on_cancelled=Mock(),
            on_unhandled_error=Mock(),
            on_finished=finished,
        )

        save_macro.assert_called_once()
        finished.assert_called_once()
        self.assertFalse(self.state.recording_flag)

    def test_rerecording_handles_cancelled_capture(self):
        cancelled = Mock()
        finished = Mock()

        self.state.recording_flag = True
        self.service.run_rerecording(
            macro_id=1,
            macro_name="macro",
            macro_duration=5,
            macro_exe="game.exe",
            registra_eventi=lambda **kwargs: None,
            update_events_only=Mock(),
            log_callback=Mock(),
            on_update_error=Mock(),
            on_cancelled=cancelled,
            on_unhandled_error=Mock(),
            on_finished=finished,
        )

        cancelled.assert_called_once()
        finished.assert_called_once()
        self.assertFalse(self.state.recording_flag)

