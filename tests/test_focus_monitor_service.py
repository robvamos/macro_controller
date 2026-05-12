import threading
import time
import unittest

from core.app_state import AppState
from services.focus_monitor_service import FocusMonitorService
from services.operation_state_service import OperationStateService


class FocusMonitorServiceTests(unittest.TestCase):
    def setUp(self):
        self.state = AppState()
        self.state_service = OperationStateService(self.state)
        self.service = FocusMonitorService(self.state, self.state_service)

    def test_check_app_focus_reports_changes(self):
        current_focus, changed = self.service.check_app_focus(active_window_id=10, app_window_id=10)
        self.assertTrue(current_focus)
        self.assertFalse(changed)

        current_focus, changed = self.service.check_app_focus(active_window_id=11, app_window_id=10)
        self.assertFalse(current_focus)
        self.assertTrue(changed)
        self.assertFalse(self.state.last_focus_state)

    def test_mark_focus_in_and_out_toggle_only_when_needed(self):
        self.assertTrue(self.service.mark_focus_out())
        self.assertFalse(self.state.last_focus_state)
        self.assertFalse(self.service.mark_focus_out())

        self.assertTrue(self.service.mark_focus_in())
        self.assertTrue(self.state.last_focus_state)
        self.assertFalse(self.service.mark_focus_in())

    def test_start_and_stop_monitoring_runs_poller(self):
        poll_calls = []
        stop_seen = threading.Event()

        def poll_focus():
            poll_calls.append(time.time())
            if len(poll_calls) >= 2:
                self.state.focus_monitor_active = False
                stop_seen.set()

        started = self.service.start_monitoring(
            is_gui_available=lambda: True,
            poll_focus=poll_focus,
            on_error=lambda exc: self.fail(f"Unexpected error: {exc}"),
            poll_interval=0.01,
        )

        self.assertTrue(started)
        self.assertTrue(stop_seen.wait(timeout=1.0))
        self.assertGreaterEqual(len(poll_calls), 2)

        stopped = self.service.stop_monitoring()
        self.assertFalse(stopped)

