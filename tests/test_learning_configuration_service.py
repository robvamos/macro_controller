from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.learning_configuration_service import LearningConfigurationService
from services.musical_convergence_service import ConvergenceProfile


class DummyAnalysis:
    dominant_bpm = 100.0
    bpm_stability_score = 82.0
    recognizable_pattern_score = 78.0
    correction_readiness_score = 75.0


class LearningConfigurationServiceTests(unittest.TestCase):
    def test_save_and_recommend_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            service = LearningConfigurationService(Path(temporary_directory) / "evaluations.json")
            summary = {
                "target_lock_pct": 76.0,
                "beat_one_accuracy_pct": 64.0,
                "resync_count": 1,
                "convergence_profile": ConvergenceProfile(
                    stage="supporting",
                    confidence_pct=71.0,
                    subtlety_pct=46.0,
                    output_intensity_pct=48.0,
                    component_complexity_pct=42.0,
                    effect_depth_pct=18.0,
                    reaction_mode="supportive",
                    should_expand_components=True,
                    should_enable_effects=True,
                    rationale="test",
                ),
            }
            snapshot = service.build_configuration_snapshot(
                sample_name="sample_a",
                analysis=DummyAnalysis(),
                learning_summary=summary,
            )
            service.save_evaluation(
                sample_name="sample_a",
                configuration_snapshot=snapshot,
                rating="ottimo",
                note="si è agganciato bene",
            )

            evaluations = service.list_evaluations_for_sample("sample_a")
            self.assertEqual(len(evaluations), 1)
            self.assertEqual(evaluations[0]["rating"], "ottimo")
            recommendation = service.recommend_for_sample("sample_a")
            self.assertIn("forte", recommendation)

    def test_build_evaluation_prompt_mentions_sample_and_scores(self) -> None:
        service = LearningConfigurationService(Path(tempfile.gettempdir()) / "ignore-learning-evaluations.json")
        prompt = service.build_evaluation_prompt(
            "sample_b",
            {
                "target_lock_pct": 55.0,
                "beat_one_accuracy_pct": 40.0,
                "convergence_profile": ConvergenceProfile(
                    stage="aligning",
                    confidence_pct=50.0,
                    subtlety_pct=72.0,
                    output_intensity_pct=24.0,
                    component_complexity_pct=18.0,
                    effect_depth_pct=6.0,
                    reaction_mode="guarded",
                    should_expand_components=False,
                    should_enable_effects=False,
                    rationale="test",
                ),
            },
        )
        self.assertIn("sample_b", prompt)
        self.assertIn("lock 55.0%", prompt)


if __name__ == "__main__":
    unittest.main()
