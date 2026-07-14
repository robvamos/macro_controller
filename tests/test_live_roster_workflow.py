import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from doomsday.intelligence.persistence import IntelligenceRepository
from doomsday.roster_live.artifact_store import RosterArtifactStore, validate_png_bytes
from doomsday.roster_live.models import ChangeDecision
from doomsday.roster_live.repository import LiveRosterRepository
from doomsday.roster_live.workflow import LiveRosterWorkflow
from doomsday.services.live_roster_service import CaptureMethod


class LiveRosterWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.repository = LiveRosterRepository(root / "live.db")
        self.workflow = LiveRosterWorkflow(
            self.repository,
            RosterArtifactStore(root / "artifacts"),
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def _session(self):
        return self.workflow.begin_session(
            runtime_id="native-windows",
            capture_method=CaptureMethod.MANUAL_SCREENSHOT,
            game_version="1.58.0",
            account_scope="test-account",
        )

    def _artifact(self, session_id, *, color=(10, 20, 30), hero_id="felix"):
        return self.workflow.register_image(
            session_id,
            image=Image.new("RGB", (120, 80), color=color),
            stage="hero_stats",
            hero_id=hero_id,
        )

    def _preview(self, *, level=60, confidence=0.92):
        session_id = self._session()
        artifact = self._artifact(session_id)
        self.workflow.ingest_fields(
            session_id,
            artifact_id=artifact.artifact_id,
            hero_id="Felix",
            fields={"display_name": "Felix", "level": level},
            field_confidences={"display_name": confidence, "level": confidence},
        )
        return self.workflow.preview(session_id)

    def test_preview_confirm_commit_is_explicit_and_atomic(self):
        preview = self._preview()

        self.assertEqual(self.repository.list_roster(), ())
        with self.assertRaises(ValueError):
            self.workflow.confirm(preview.change_set_id)

        for item in preview.items:
            self.workflow.decide(
                preview.change_set_id,
                item_id=item.item_id,
                decision=ChangeDecision.ACCEPTED,
            )
        confirmed = self.workflow.confirm(preview.change_set_id)
        result = self.workflow.commit(
            preview.change_set_id,
            expected_base_revision=confirmed.base_revision,
        )

        self.assertEqual(result.applied_items, 2)
        roster = self.repository.list_roster()
        self.assertEqual(roster[0]["display_name"], "Felix")
        self.assertEqual(roster[0]["facts"]["level"]["value"], 60)
        self.assertEqual(len(self.repository.pending_outbox()), 2)

    def test_commit_retry_is_idempotent(self):
        preview = self._preview()
        for item in preview.items:
            self.workflow.decide(
                preview.change_set_id, item_id=item.item_id, decision=ChangeDecision.ACCEPTED
            )
        self.workflow.confirm(preview.change_set_id)

        first = self.workflow.commit(preview.change_set_id, expected_base_revision=0)
        second = self.workflow.commit(preview.change_set_id, expected_base_revision=0)

        self.assertEqual(first.revision_id, second.revision_id)
        self.assertTrue(second.idempotent_replay)
        self.assertEqual(len(self.repository.list_roster()), 1)

    def test_stale_preview_is_rejected_by_optimistic_lock(self):
        first = self._preview(level=60)
        second = self._preview(level=61)
        for preview in (first, second):
            for item in preview.items:
                self.workflow.decide(
                    preview.change_set_id, item_id=item.item_id, decision=ChangeDecision.ACCEPTED
                )
            self.workflow.confirm(preview.change_set_id)

        self.workflow.commit(first.change_set_id, expected_base_revision=0)
        with self.assertRaises(RuntimeError):
            self.workflow.commit(second.change_set_id, expected_base_revision=0)

        roster = self.repository.list_roster()
        self.assertEqual(roster[0]["facts"]["level"]["value"], 60)

    def test_conflicting_candidates_are_preserved_in_preview(self):
        session_id = self._session()
        artifact = self._artifact(session_id)
        for value, confidence in ((60, 0.7), (61, 0.8)):
            self.workflow.ingest_fields(
                session_id,
                artifact_id=artifact.artifact_id,
                hero_id="Felix",
                fields={"level": value},
                field_confidences={"level": confidence},
            )

        preview = self.workflow.preview(session_id)

        self.assertTrue(preview.items[0].conflict)
        self.assertEqual(preview.items[0].proposed_value, 61)
        self.assertEqual(len(preview.items[0].alternatives), 2)
        self.assertEqual(preview.items[0].decision, ChangeDecision.UNRESOLVED)

    def test_reject_and_manual_override_are_respected(self):
        preview = self._preview(level=59, confidence=0.4)
        for item in preview.items:
            if item.field_name == "level":
                self.workflow.decide(
                    preview.change_set_id,
                    item_id=item.item_id,
                    decision=ChangeDecision.MANUAL_OVERRIDE,
                    override_value=60,
                    reason="Verificato visivamente",
                )
            else:
                self.workflow.decide(
                    preview.change_set_id,
                    item_id=item.item_id,
                    decision=ChangeDecision.REJECTED,
                )
        self.workflow.confirm(preview.change_set_id)
        result = self.workflow.commit(preview.change_set_id, expected_base_revision=0)

        self.assertEqual(result.applied_items, 1)
        self.assertEqual(result.rejected_items, 1)
        self.assertEqual(self.repository.list_roster()[0]["facts"]["level"]["value"], 60)

    def test_artifact_is_deduplicated_and_has_valid_hash(self):
        session_id = self._session()
        first = self._artifact(session_id)
        second = self._artifact(session_id)

        self.assertEqual(first.artifact_id, second.artifact_id)
        self.assertEqual(first.sha256, second.sha256)
        self.assertTrue(Path(first.path).exists())
        self.assertEqual(validate_png_bytes(Path(first.path).read_bytes()), (120, 80))

    def test_outbox_publishing_is_idempotent(self):
        preview = self._preview()
        for item in preview.items:
            self.workflow.decide(
                preview.change_set_id, item_id=item.item_id, decision=ChangeDecision.ACCEPTED
            )
        self.workflow.confirm(preview.change_set_id)
        self.workflow.commit(preview.change_set_id, expected_base_revision=0)
        intelligence = IntelligenceRepository(Path(self.tempdir.name) / "intelligence.db")

        first = self.workflow.publish_evidence(intelligence)
        second = self.workflow.publish_evidence(intelligence)

        self.assertEqual(first, {"published": 2, "failed": 0})
        self.assertEqual(second, {"published": 0, "failed": 0})
        rows = intelligence.list_contributions(subject_id="hero:felix", field_name="level")
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
