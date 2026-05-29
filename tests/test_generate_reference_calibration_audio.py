from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_reference_calibration_audio.py"
SPEC = importlib.util.spec_from_file_location("generate_reference_calibration_audio", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class GenerateReferenceCalibrationAudioTests(unittest.TestCase):
    def test_assemble_reference_audio_matches_expected_duration(self) -> None:
        audio, metadata = MODULE.assemble_reference_audio(MODULE.DEFAULT_SEGMENTS)

        expected_duration = sum(segment["duration_sec"] for segment in MODULE.DEFAULT_SEGMENTS)
        self.assertEqual(len(metadata), len(MODULE.DEFAULT_SEGMENTS))
        self.assertEqual(len(audio), expected_duration * MODULE.SAMPLE_RATE)
        self.assertEqual(metadata[0]["bpm"], 90)
        self.assertFalse(metadata[1]["expected_detection"])

    def test_sanitize_base_name_replaces_invalid_characters(self) -> None:
        self.assertEqual(MODULE.sanitize_base_name(" generic sample v1 "), "generic_sample_v1")

        with self.assertRaises(ValueError):
            MODULE.sanitize_base_name("   ")

    def test_manifest_upsert_replaces_existing_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / MODULE.MANIFEST_NAME

            MODULE.upsert_manifest_entry(
                manifest_path,
                {
                    "base_name": "sample_one",
                    "preset": "generic_reference",
                    "description": "first",
                    "duration_sec": 180,
                    "sample_rate": MODULE.SAMPLE_RATE,
                    "generated_at": "2026-05-28T00:00:00+00:00",
                    "mp3": "a.mp3",
                    "wav": "a.wav",
                    "ground_truth": "a.json",
                },
            )
            MODULE.upsert_manifest_entry(
                manifest_path,
                {
                    "base_name": "sample_one",
                    "preset": "reference_live_calibration",
                    "description": "updated",
                    "duration_sec": 180,
                    "sample_rate": MODULE.SAMPLE_RATE,
                    "generated_at": "2026-05-28T01:00:00+00:00",
                    "mp3": "b.mp3",
                    "wav": "b.wav",
                    "ground_truth": "b.json",
                },
            )

            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["files"]), 1)
            self.assertEqual(payload["files"][0]["preset"], "reference_live_calibration")
            self.assertEqual(payload["files"][0]["mp3"], "b.mp3")

    def test_prebuilt_library_exposes_at_least_three_test_presets(self) -> None:
        self.assertGreaterEqual(len(MODULE.PRESETS), 3)
        self.assertIn("phase_alignment_drill", MODULE.PRESETS)
        self.assertIn("grid16_phrase_map", MODULE.PRESETS)
        self.assertIn("tempo_transition_stress", MODULE.PRESETS)


if __name__ == "__main__":
    unittest.main()
