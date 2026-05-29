from __future__ import annotations

import math
import unittest

import numpy as np

from services.preprocessing_pipeline_service import PreprocessingPipelineService


class PreprocessingPipelineServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PreprocessingPipelineService()
        self.sample_rate = 44_100

    def _build_click_track(self, bpm: float, duration_sec: float) -> np.ndarray:
        total_samples = int(duration_sec * self.sample_rate)
        signal = np.zeros(total_samples, dtype=np.float32)
        beat_interval = int((60.0 / bpm) * self.sample_rate)
        click_len = int(0.03 * self.sample_rate)
        time_axis = np.arange(click_len, dtype=np.float32) / self.sample_rate
        click = 0.9 * np.sin(2.0 * math.pi * 1800.0 * time_axis) * np.exp(-time_axis * 35.0)
        for start in range(0, total_samples - click_len, beat_interval):
            signal[start : start + click_len] += click.astype(np.float32)
        return signal

    def test_analyze_bpm_windows_detects_stable_bpm(self) -> None:
        audio = self._build_click_track(120.0, 16.0)
        analysis = self.service.analyze_bpm_windows(
            sample_name="stable_120",
            audio=audio,
            sample_rate=self.sample_rate,
            window_sec=6.0,
            hop_sec=3.0,
        )

        self.assertGreater(analysis.dominant_bpm, 110.0)
        self.assertLess(analysis.dominant_bpm, 130.0)
        self.assertGreater(len(analysis.windows), 1)
        self.assertGreater(analysis.bpm_stability_score, 70.0)

    def test_merge_windows_to_segments_groups_similar_bpms(self) -> None:
        analysis = self.service.merge_windows_to_segments(
            [
                type("Window", (), {"start_sec": 0.0, "end_sec": 4.0, "bpm": 99.0, "confidence": 0.8})(),
                type("Window", (), {"start_sec": 4.0, "end_sec": 8.0, "bpm": 100.5, "confidence": 0.7})(),
                type("Window", (), {"start_sec": 8.0, "end_sec": 12.0, "bpm": 112.0, "confidence": 0.9})(),
            ]
        )

        self.assertEqual(len(analysis), 2)
        self.assertEqual(analysis[0]["start_sec"], 0.0)
        self.assertEqual(analysis[0]["end_sec"], 8.0)
        self.assertEqual(analysis[1]["start_sec"], 8.0)


if __name__ == "__main__":
    unittest.main()
