from __future__ import annotations

import unittest

from services.learning_test_service import LearningTestService


class LearningTestServiceTests(unittest.TestCase):
    def test_build_learning_grid_assigns_higher_weight_to_beat_one(self) -> None:
        payload = {
            "segments": [
                {
                    "label": "tempo_90",
                    "kind": "tempo",
                    "start_sec": 0.0,
                    "end_sec": 4.0,
                    "duration_sec": 4.0,
                    "bpm": 60,
                    "expected_detection": True,
                }
            ]
        }
        service = LearningTestService()
        grid = service.build_learning_grid("sample", payload)

        self.assertEqual(len(grid), 4)
        self.assertEqual(grid[0].beat_in_bar, 1)
        self.assertGreater(grid[0].weight, grid[1].weight)
        self.assertLess(grid[0].phase_tolerance_ms, grid[1].phase_tolerance_ms)

    def test_record_observation_updates_status_and_summary(self) -> None:
        payload = {
            "segments": [
                {
                    "label": "tempo_90",
                    "kind": "tempo",
                    "start_sec": 0.0,
                    "end_sec": 8.0,
                    "duration_sec": 8.0,
                    "bpm": 60,
                    "expected_detection": True,
                }
            ]
        }
        service = LearningTestService()
        service.start_session("sample", payload)
        service.record_observation(offset_ms=25.0, confidence=0.8, observed_beat_in_bar=1)
        service.record_observation(offset_ms=15.0, confidence=0.9, observed_beat_in_bar=2)
        service.record_observation(offset_ms=10.0, confidence=0.9, observed_beat_in_bar=3)
        service.record_observation(offset_ms=-5.0, confidence=0.95, observed_beat_in_bar=4)
        service.record_observation(offset_ms=3.0, confidence=0.95, observed_beat_in_bar=1)

        summary = service.get_summary()
        self.assertEqual(summary["status"], "tracking")
        self.assertGreater(summary["target_lock_pct"], 0.0)
        self.assertIn(summary["correction_speed"], {"warming_up", "fast", "improving", "slow"})
        self.assertGreater(summary["beat_one_accuracy_pct"], 0.0)
        self.assertIn(summary["convergence_profile"].stage, {"listening", "aligning", "supporting", "assertive"})

    def test_reset_sync_and_feedback_are_reflected(self) -> None:
        payload = {
            "segments": [
                {
                    "label": "tempo_90",
                    "kind": "tempo",
                    "start_sec": 0.0,
                    "end_sec": 4.0,
                    "duration_sec": 4.0,
                    "bpm": 60,
                    "expected_detection": True,
                }
            ]
        }
        service = LearningTestService()
        service.start_session("sample", payload)
        service.apply_feedback("too_slow")
        service.reset_sync(cut_current_bar=True, reason="manual")

        summary = service.get_summary()
        self.assertEqual(summary["resync_count"], 1)
        self.assertEqual(summary["cut_bar_count"], 1)
        self.assertEqual(summary["status"], "resync:manual")


if __name__ == "__main__":
    unittest.main()
