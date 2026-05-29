from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import soundfile as sf

from services import audio_sample_service


class AudioSampleServiceTests(unittest.TestCase):
    def test_validate_time_selection_rejects_invalid_ranges(self) -> None:
        with self.assertRaises(ValueError):
            audio_sample_service.validate_time_selection(-1.0, 2.0, 10.0)
        with self.assertRaises(ValueError):
            audio_sample_service.validate_time_selection(2.0, 2.0, 10.0)
        with self.assertRaises(ValueError):
            audio_sample_service.validate_time_selection(2.0, 11.0, 10.0)

    def test_create_audio_sample_from_selection_updates_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_dir = Path(temporary_directory)
            source_path = temp_dir / "source.wav"
            output_dir = temp_dir / "calibration"

            duration_sec = 4.0
            sample_rate = 44_100
            samples = np.linspace(-0.5, 0.5, int(duration_sec * sample_rate), dtype=np.float32)
            sf.write(source_path, samples, sample_rate)

            def fake_encode(_ffmpeg_exe, wav_path, mp3_path):
                mp3_path.write_bytes(b"fake-mp3")

            with mock.patch.object(audio_sample_service, "resolve_ffmpeg_executable", return_value=Path("ffmpeg.exe")):
                with mock.patch.object(audio_sample_service, "encode_wav_to_mp3", side_effect=fake_encode):
                    entry = audio_sample_service.create_audio_sample_from_selection(
                        source_path=source_path,
                        output_name="chosen section",
                        start_sec=1.0,
                        end_sec=2.5,
                        output_dir=output_dir,
                    )

            self.assertEqual(entry["base_name"], "chosen_section")
            self.assertTrue((output_dir / "chosen_section.wav").exists())
            self.assertTrue((output_dir / "chosen_section.mp3").exists())

            payload = json.loads((output_dir / "chosen_section.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["preset"], audio_sample_service.DEFAULT_IMPORTED_PRESET)
            self.assertEqual(payload["notes"]["selection_start_sec"], 1.0)
            self.assertEqual(payload["notes"]["selection_end_sec"], 2.5)

            manifest = json.loads((output_dir / audio_sample_service.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["files"]), 1)
            self.assertEqual(manifest["files"][0]["base_name"], "chosen_section")
            self.assertTrue(manifest["files"][0]["source_file"].endswith("source.wav"))

    def test_split_audio_sample_creates_one_file_per_segment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_dir = Path(temporary_directory)
            output_dir = temp_dir / "calibration"
            output_dir.mkdir(parents=True, exist_ok=True)

            source_audio = np.linspace(-0.25, 0.25, int(4.0 * audio_sample_service.SAMPLE_RATE), dtype=np.float32)
            sf.write(output_dir / "pattern.wav", source_audio, audio_sample_service.SAMPLE_RATE)
            (output_dir / "pattern.json").write_text(
                json.dumps(
                    {
                        "preset": "test_pattern",
                        "description": "pattern",
                        "sample_rate": audio_sample_service.SAMPLE_RATE,
                        "total_duration_sec": 4.0,
                        "segments": [
                            {"label": "bar_a", "kind": "tempo", "start_sec": 0.0, "end_sec": 1.5, "duration_sec": 1.5, "bpm": 90, "expected_detection": True},
                            {"label": "bar_b", "kind": "pause", "start_sec": 1.5, "end_sec": 4.0, "duration_sec": 2.5, "bpm": None, "expected_detection": False},
                        ],
                        "notes": {},
                    }
                ),
                encoding="utf-8",
            )
            audio_sample_service.upsert_manifest_entry(
                output_dir / audio_sample_service.MANIFEST_NAME,
                {
                    "base_name": "pattern",
                    "preset": "test_pattern",
                    "description": "pattern",
                    "duration_sec": 4.0,
                    "sample_rate": audio_sample_service.SAMPLE_RATE,
                    "generated_at": "2026-05-28T00:00:00+00:00",
                    "mp3": str((output_dir / "pattern.mp3").resolve()),
                    "wav": str((output_dir / "pattern.wav").resolve()),
                    "ground_truth": str((output_dir / "pattern.json").resolve()),
                },
            )

            def fake_encode(_ffmpeg_exe, wav_path, mp3_path):
                mp3_path.write_bytes(b"fake-mp3")

            with mock.patch.object(audio_sample_service, "resolve_ffmpeg_executable", return_value=Path("ffmpeg.exe")):
                with mock.patch.object(audio_sample_service, "encode_wav_to_mp3", side_effect=fake_encode):
                    entries = audio_sample_service.split_audio_sample(base_name="pattern", output_dir=output_dir)

            self.assertEqual(len(entries), 2)
            self.assertTrue((output_dir / "pattern_01_bar_a.wav").exists())
            self.assertTrue((output_dir / "pattern_02_bar_b.wav").exists())

    def test_compose_test_song_preserves_selected_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_dir = Path(temporary_directory)
            output_dir = temp_dir / "calibration"
            output_dir.mkdir(parents=True, exist_ok=True)

            for base_name, amplitude, bpm in (("first", 0.1, 90), ("second", 0.2, 100)):
                audio = np.full(int(1.0 * audio_sample_service.SAMPLE_RATE), amplitude, dtype=np.float32)
                sf.write(output_dir / f"{base_name}.wav", audio, audio_sample_service.SAMPLE_RATE)
                (output_dir / f"{base_name}.json").write_text(
                    json.dumps(
                        {
                            "preset": "test",
                            "description": base_name,
                            "sample_rate": audio_sample_service.SAMPLE_RATE,
                            "total_duration_sec": 1.0,
                            "segments": [
                                {
                                    "label": base_name,
                                    "kind": "tempo",
                                    "start_sec": 0.0,
                                    "end_sec": 1.0,
                                    "duration_sec": 1.0,
                                    "bpm": bpm,
                                    "expected_detection": True,
                                }
                            ],
                            "notes": {},
                        }
                    ),
                    encoding="utf-8",
                )
                audio_sample_service.upsert_manifest_entry(
                    output_dir / audio_sample_service.MANIFEST_NAME,
                    {
                        "base_name": base_name,
                        "preset": "test",
                        "description": base_name,
                        "duration_sec": 1.0,
                        "sample_rate": audio_sample_service.SAMPLE_RATE,
                        "generated_at": "2026-05-28T00:00:00+00:00",
                        "mp3": str((output_dir / f"{base_name}.mp3").resolve()),
                        "wav": str((output_dir / f"{base_name}.wav").resolve()),
                        "ground_truth": str((output_dir / f"{base_name}.json").resolve()),
                    },
                )

            def fake_encode(_ffmpeg_exe, wav_path, mp3_path):
                mp3_path.write_bytes(b"fake-mp3")

            with mock.patch.object(audio_sample_service, "resolve_ffmpeg_executable", return_value=Path("ffmpeg.exe")):
                with mock.patch.object(audio_sample_service, "encode_wav_to_mp3", side_effect=fake_encode):
                    entry = audio_sample_service.compose_test_song(
                        sample_names=["second", "first"],
                        output_name="ordered_song",
                        output_dir=output_dir,
                        gap_sec=0.5,
                    )

            payload = json.loads((output_dir / "ordered_song.json").read_text(encoding="utf-8"))
            self.assertEqual(entry["base_name"], "ordered_song")
            self.assertEqual(payload["notes"]["component_samples"], ["second", "first"])
            self.assertEqual(payload["segments"][0]["source_sample"], "second")
            self.assertEqual(payload["segments"][2]["source_sample"], "first")


if __name__ == "__main__":
    unittest.main()
