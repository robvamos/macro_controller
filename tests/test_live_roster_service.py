import tempfile
import unittest
from pathlib import Path

from PIL import Image

from doomsday.services.live_roster_service import (
    CaptureMethod,
    LiveRosterAcquisitionService,
    RosterCaptureSession,
    RosterObservation,
)


class _FakeProvider:
    runtime_id = "test-runtime"
    capture_method = CaptureMethod.MANUAL_SCREENSHOT

    def capture_frame(self):
        return Image.new("RGB", (80, 40), color=(10, 20, 30))


class LiveRosterServiceTests(unittest.TestCase):
    def test_capture_writes_only_to_explicit_destination(self):
        with tempfile.TemporaryDirectory() as tempdir:
            destination = Path(tempdir) / "capture.png"
            result = LiveRosterAcquisitionService().capture_supervised_frame(
                _FakeProvider(), destination=destination
            )

            self.assertEqual(result, destination)
            with Image.open(result) as image:
                self.assertEqual(image.size, (80, 40))

    def test_observation_emits_atomic_first_party_contributions(self):
        observation = RosterObservation(
            hero_id="felix",
            fields={"level": 60, "stars": 6},
            confidence=0.93,
            observed_at="2026-07-14T12:00:00+00:00",
            source_ref="capture://felix-overview.png",
            capture_method=CaptureMethod.NATIVE_WIN32,
            runtime_id="native-windows",
            game_version="1.58.0",
        )

        contributions = observation.to_contributions()

        self.assertEqual(len(contributions), 2)
        self.assertEqual({item.field_name for item in contributions}, {"level", "stars"})
        self.assertTrue(all(item.provider_type == "first-party-game-ui" for item in contributions))
        self.assertTrue(all(item.game_version == "1.58.0" for item in contributions))

    def test_session_rejects_observation_from_other_runtime(self):
        session = RosterCaptureSession("native-windows", CaptureMethod.NATIVE_WIN32)
        observation = RosterObservation(
            hero_id="felix",
            fields={"level": 60},
            confidence=0.9,
            observed_at="2026-07-14T12:00:00+00:00",
            source_ref="capture://felix.png",
            capture_method=CaptureMethod.NATIVE_WIN32,
            runtime_id="bluestacks5",
        )

        with self.assertRaises(ValueError):
            session.add_observation(observation)

    def test_ocr_adapter_does_not_publish_unobserved_default_zeroes(self):
        observation = LiveRosterAcquisitionService().observation_from_ocr_text(
            hero_id="felix",
            ocr_text="ATK: 1234\nDEF: 987\nHP: 4567\nSPD: 112",
            source_ref="capture://felix-stats.png",
            capture_method=CaptureMethod.NATIVE_WIN32,
            runtime_id="native-windows",
            observed_at="2026-07-14T12:00:00+00:00",
        )

        self.assertEqual(observation.fields["ATK"], 1234)
        self.assertNotIn("Squadre", observation.fields)

    def test_ocr_adapter_rejects_empty_or_unreadable_text(self):
        with self.assertRaises(ValueError):
            LiveRosterAcquisitionService().observation_from_ocr_text(
                hero_id="felix",
                ocr_text="",
                source_ref="capture://empty.png",
                capture_method=CaptureMethod.NATIVE_WIN32,
                runtime_id="native-windows",
            )


if __name__ == "__main__":
    unittest.main()
