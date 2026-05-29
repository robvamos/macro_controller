import threading
import time
import unittest
from unittest.mock import Mock, patch

import task_controller


class TaskControllerShutdownTests(unittest.TestCase):
    def setUp(self):
        task_controller.scheduler_active = False
        task_controller.scheduler_thread = None
        task_controller._scheduler_stop_event.clear()
        with task_controller._worker_threads_lock:
            task_controller._worker_threads.clear()

    def tearDown(self):
        task_controller.scheduler_active = False
        task_controller._scheduler_stop_event.set()
        if task_controller.scheduler_thread and task_controller.scheduler_thread.is_alive():
            task_controller.scheduler_thread.join(timeout=1.0)
        task_controller.scheduler_thread = None
        task_controller._join_worker_threads()
        with task_controller._worker_threads_lock:
            task_controller._worker_threads.clear()
        task_controller._scheduler_stop_event.clear()

    def test_wait_or_cancel_returns_true_when_shutdown_requested(self):
        task_controller._scheduler_stop_event.set()
        self.assertTrue(task_controller._wait_or_cancel(0.5))

    def test_stop_scheduler_signals_and_joins_registered_workers(self):
        task_controller.scheduler_active = True

        scheduler_thread = threading.Thread(
            target=lambda: task_controller._scheduler_stop_event.wait(5.0),
            daemon=True,
            name="test-scheduler-loop",
        )
        scheduler_thread.start()
        task_controller.scheduler_thread = scheduler_thread

        worker_released = threading.Event()

        def worker_target():
            try:
                task_controller._wait_or_cancel(5.0)
            finally:
                worker_released.set()

        worker_thread = task_controller._start_worker_thread(
            target=worker_target,
            name="test-worker-thread",
        )

        log_callback = Mock()
        with patch.object(task_controller, "request_playback_stop") as request_stop:
            task_controller.stop_scheduler(log_callback=log_callback)

        request_stop.assert_called_once_with(log_callback)
        self.assertFalse(task_controller.scheduler_active)
        self.assertIsNone(task_controller.scheduler_thread)
        self.assertTrue(worker_released.wait(timeout=1.0))
        self.assertFalse(worker_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
