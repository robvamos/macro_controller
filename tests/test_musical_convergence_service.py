from __future__ import annotations

import unittest

from services.musical_convergence_service import MusicalConvergenceService


class MusicalConvergenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MusicalConvergenceService()

    def test_low_confidence_profile_stays_non_invasive(self) -> None:
        profile = self.service.build_profile(
            recognizable_pattern_score=10.0,
            bpm_stability_score=15.0,
            correction_readiness_score=18.0,
            target_lock_pct=5.0,
            beat_one_accuracy_pct=0.0,
            resync_count=2,
        )

        self.assertEqual(profile.stage, "listening")
        self.assertLess(profile.output_intensity_pct, 15.0)
        self.assertFalse(profile.should_enable_effects)

    def test_high_confidence_profile_expands_presence(self) -> None:
        profile = self.service.build_profile(
            recognizable_pattern_score=92.0,
            bpm_stability_score=95.0,
            correction_readiness_score=88.0,
            target_lock_pct=91.0,
            beat_one_accuracy_pct=84.0,
            resync_count=0,
        )

        self.assertEqual(profile.stage, "assertive")
        self.assertGreater(profile.output_intensity_pct, 70.0)
        self.assertTrue(profile.should_expand_components)
        self.assertTrue(profile.should_enable_effects)


if __name__ == "__main__":
    unittest.main()
