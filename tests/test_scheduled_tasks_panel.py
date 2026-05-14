import datetime
import unittest

from ui.scheduled_tasks_panel import build_countdown_entries


class ScheduledTasksPanelTests(unittest.TestCase):
    def test_build_countdown_entries_includes_runtime_status(self):
        now = datetime.datetime(2026, 5, 14, 12, 0, 0)
        active_tasks = [
            {
                "id": 1,
                "nome": "Task Alpha",
                "macro_nome": "Macro A",
                "prossima_esecuzione": "2026-05-14 12:01:30",
            }
        ]

        entries = build_countdown_entries(
            active_tasks,
            lambda _task_id: [],
            now=now,
            runtime_status={
                "scheduler_active": True,
                "currently_executing_task_name": "Task Alpha",
            },
        )

        text = "".join(part for part, _ in entries)
        self.assertIn("Scheduler attivo", text)
        self.assertIn("In esecuzione: Task Alpha", text)
        self.assertIn("Task Alpha", text)
        self.assertIn("01m 30s", text)

    def test_build_countdown_entries_handles_no_active_tasks(self):
        entries = build_countdown_entries(
            [],
            lambda _task_id: [],
            now=datetime.datetime(2026, 5, 14, 12, 0, 0),
            runtime_status={"scheduler_active": False},
        )

        text = "".join(part for part, _ in entries)
        self.assertIn("Scheduler fermo", text)
        self.assertIn("Nessun task attivo", text)


if __name__ == "__main__":
    unittest.main()
