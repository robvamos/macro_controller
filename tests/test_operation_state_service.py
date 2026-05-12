import unittest

from core.app_state import AppState
from services.operation_state_service import OperationStateService


class OperationStateServiceTests(unittest.TestCase):
    def setUp(self):
        self.state = AppState()
        self.service = OperationStateService(self.state)

    def test_start_playback_updates_state(self):
        self.service.start_playback(loop_enabled=True, target_exe="game.exe")

        self.assertTrue(self.state.playing_flag)
        self.assertTrue(self.state.running_loop)
        self.assertEqual(self.state.current_target_exe, "game.exe")

    def test_reset_playback_clears_flags(self):
        self.state.playing_flag = True
        self.state.running_loop = True
        self.state.current_target_exe = "game.exe"

        self.service.reset_playback()

        self.assertFalse(self.state.playing_flag)
        self.assertFalse(self.state.running_loop)
        self.assertIsNone(self.state.current_target_exe)

    def test_recording_timer_start_and_stop(self):
        self.service.start_recording_timer(12)

        self.assertTrue(self.state.recording_timer_active)
        self.assertEqual(self.state.recording_duration, 12)
        self.assertIsNotNone(self.state.recording_start_time)

        self.service.set_recording_timer_job("job-1")
        self.service.stop_recording_timer()

        self.assertFalse(self.state.recording_timer_active)
        self.assertEqual(self.state.recording_duration, 0)
        self.assertIsNone(self.state.recording_start_time)
        self.assertIsNone(self.state.recording_timer_job)

    def test_focus_state_and_monitor_tracking(self):
        self.service.set_focus_monitoring(True, thread="thread-ref")
        self.service.set_focus_state(False)

        self.assertTrue(self.state.focus_monitor_active)
        self.assertEqual(self.state.focus_monitor_thread, "thread-ref")
        self.assertFalse(self.state.last_focus_state)

        self.service.set_focus_monitoring(False, None)

        self.assertFalse(self.state.focus_monitor_active)
        self.assertIsNone(self.state.focus_monitor_thread)

