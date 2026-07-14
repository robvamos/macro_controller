import json
import tempfile
import unittest
from pathlib import Path

from services.learning_session_journal_service import (
    append_learning_event,
    finalize_learning_session_journal,
    initialize_learning_session_journal,
    learning_session_directory,
)


class LearningSessionJournalServiceTests(unittest.TestCase):
    def test_incremental_journal_survives_before_finalization(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            initialize_learning_session_journal(
                session_name="Hero demo",
                scenario="hero_inspection",
                objective="Inspect hero",
                declared_workflow_id="hero-inspection-v1",
                window_rect=(10, 20, 110, 220),
                root=root,
            )
            append_learning_event(
                session_name="Hero demo",
                event={"sequence_index": 1, "game_element_id": 42},
                root=root,
            )

            session_dir = learning_session_directory("Hero demo", root=root)
            manifest = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
            event = json.loads((session_dir / "events.jsonl").read_text(encoding="utf-8"))

            self.assertEqual(manifest["status"], "recording")
            self.assertEqual(manifest["window_rect"]["left"], 10)
            self.assertEqual(event["game_element_id"], 42)

    def test_finalize_updates_manifest_without_rewriting_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            initialize_learning_session_journal(
                session_name="Hero demo",
                scenario="hero_inspection",
                objective="Inspect hero",
                declared_workflow_id="hero-inspection-v1",
                window_rect=None,
                root=root,
            )
            append_learning_event(
                session_name="Hero demo",
                event={"sequence_index": 1},
                root=root,
            )
            manifest_path = finalize_learning_session_journal(
                session_name="Hero demo",
                status="completed",
                click_count=1,
                macro_id=77,
                root=root,
            )

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["macro_id"], 77)
            self.assertEqual(manifest["click_count"], 1)


if __name__ == "__main__":
    unittest.main()
