from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.audio_sample_service import (
    DEFAULT_OUTPUT_DIR,
    MANIFEST_NAME,
    SAMPLE_RATE,
    load_manifest,
    sanitize_base_name,
    upsert_manifest_entry,
)


DEFAULT_SEGMENTS = [
    {"label": "tempo_90", "kind": "tempo", "duration_sec": 50, "bpm": 90},
    {"label": "pause_noise_10", "kind": "pause", "duration_sec": 10, "noise_level": 0.025},
    {"label": "tempo_100", "kind": "tempo", "duration_sec": 50, "bpm": 100},
    {"label": "pause_noise_20", "kind": "pause", "duration_sec": 20, "noise_level": 0.03},
    {"label": "tempo_105", "kind": "tempo", "duration_sec": 50, "bpm": 105},
]

PHASE_ALIGNMENT_SEGMENTS = [
    {"label": "phase_block_1", "kind": "tempo", "duration_sec": 20, "bpm": 96},
    {"label": "phase_block_2", "kind": "tempo", "duration_sec": 20, "bpm": 96},
    {"label": "phase_pause", "kind": "pause", "duration_sec": 8, "noise_level": 0.02},
    {"label": "phase_block_3", "kind": "tempo", "duration_sec": 20, "bpm": 96},
    {"label": "phase_block_4", "kind": "tempo", "duration_sec": 20, "bpm": 96},
]

GRID16_SEGMENTS = [
    {"label": "grid16_a", "kind": "tempo", "duration_sec": 24, "bpm": 92},
    {"label": "grid16_b", "kind": "tempo", "duration_sec": 24, "bpm": 92},
    {"label": "grid16_c", "kind": "tempo", "duration_sec": 24, "bpm": 104},
    {"label": "grid16_d", "kind": "tempo", "duration_sec": 24, "bpm": 104},
]

TEMPO_TRANSITION_SEGMENTS = [
    {"label": "tempo_88_intro", "kind": "tempo", "duration_sec": 36, "bpm": 88},
    {"label": "tempo_98_bridge", "kind": "tempo", "duration_sec": 36, "bpm": 98},
    {"label": "pause_noise_6", "kind": "pause", "duration_sec": 6, "noise_level": 0.018},
    {"label": "tempo_108_push", "kind": "tempo", "duration_sec": 36, "bpm": 108},
]

PRESETS = {
    "generic_reference": {
        "base_name": "generic_reference_sample",
        "description": "Generic prebuilt sample for latency, preprocessing, and BPM tracking tests.",
        "notes": {
            "purpose": "Generic prebuilt sample for live preprocessing checks and known-pattern testing.",
            "tempo_segments_bpm": [90, 100, 105],
            "pause_segments_sec": [10, 20],
        },
        "segments": DEFAULT_SEGMENTS,
    },
    "reference_live_calibration": {
        "base_name": "reference_live_calibration",
        "description": "Reference sample for live preprocessing, latency calibration, and BPM tracking.",
        "notes": {
            "purpose": "Reference file for live preprocessing, latency calibration, and BPM tracking.",
            "tempo_segments_bpm": [90, 100, 105],
            "pause_segments_sec": [10, 20],
        },
        "segments": DEFAULT_SEGMENTS,
    },
    "phase_alignment_drill": {
        "base_name": "phase_alignment_drill",
        "description": "Steady 96 BPM piece with known 4-bar blocks for bar-phase verification.",
        "notes": {
            "purpose": "Test rapid rhythmic alignment and bar-start recognition on stable material.",
            "tempo_segments_bpm": [96, 96, 96, 96],
            "bars_per_section": [8, 8, 8, 8],
            "phase_focus": "Recognize recurring beat one across repeated sections.",
        },
        "segments": PHASE_ALIGNMENT_SEGMENTS,
    },
    "grid16_phrase_map": {
        "base_name": "grid16_phrase_map",
        "description": "Known 16-grid phrase map with two tempo zones for structural alignment checks.",
        "notes": {
            "purpose": "Verify phrase tracking across a 16-grid song form and detect section boundaries.",
            "tempo_segments_bpm": [92, 92, 104, 104],
            "grid_blocks": 16,
            "bars_per_section": [8, 8, 8, 8],
            "phase_focus": "Track phrase continuity before full beat-one phase estimation.",
        },
        "segments": GRID16_SEGMENTS,
    },
    "tempo_transition_stress": {
        "base_name": "tempo_transition_stress",
        "description": "Three known tempo regions with a short pause to test fast re-alignment.",
        "notes": {
            "purpose": "Measure how quickly the rhythmic alignment stage re-locks after tempo shifts.",
            "tempo_segments_bpm": [88, 98, 108],
            "pause_segments_sec": [6],
            "phase_focus": "Observe whether the system stays balanced during fast correction.",
        },
        "segments": TEMPO_TRANSITION_SEGMENTS,
    },
}


def generate_click(length_samples: int, amplitude: float, frequency_hz: float = 1800.0) -> np.ndarray:
    t = np.arange(length_samples, dtype=np.float32) / SAMPLE_RATE
    envelope = np.exp(-t * 35.0).astype(np.float32)
    waveform = np.sin(2.0 * math.pi * frequency_hz * t).astype(np.float32)
    return amplitude * envelope * waveform


def build_tempo_segment(duration_sec: int, bpm: float) -> np.ndarray:
    total_samples = int(duration_sec * SAMPLE_RATE)
    segment = np.zeros(total_samples, dtype=np.float32)
    beat_interval_samples = int((60.0 / bpm) * SAMPLE_RATE)
    click_length = int(0.06 * SAMPLE_RATE)
    normal_click = generate_click(click_length, amplitude=0.6)
    accent_click = generate_click(click_length, amplitude=0.9, frequency_hz=2200.0)

    beat_index = 0
    for start in range(0, total_samples, beat_interval_samples):
        click = accent_click if beat_index % 4 == 0 else normal_click
        end = min(total_samples, start + click_length)
        segment[start:end] += click[: end - start]
        beat_index += 1

    bed_frequency = 110.0 + (bpm - 90.0) * 3.0
    t = np.arange(total_samples, dtype=np.float32) / SAMPLE_RATE
    segment += 0.03 * np.sin(2.0 * math.pi * bed_frequency * t).astype(np.float32)
    return segment


def build_pause_segment(duration_sec: int, noise_level: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    total_samples = int(duration_sec * SAMPLE_RATE)
    white = rng.normal(0.0, 1.0, total_samples).astype(np.float32)
    kernel = np.ones(512, dtype=np.float32) / 512.0
    smoothed = np.convolve(white, kernel, mode="same")
    tone = 0.005 * np.sin(2.0 * math.pi * 230.0 * np.arange(total_samples, dtype=np.float32) / SAMPLE_RATE)
    return (noise_level * smoothed + tone).astype(np.float32)


def assemble_reference_audio(segments: list[dict]) -> tuple[np.ndarray, list[dict]]:
    parts = []
    metadata = []
    cursor = 0.0

    for index, segment in enumerate(segments):
        if segment["kind"] == "tempo":
            samples = build_tempo_segment(segment["duration_sec"], segment["bpm"])
        else:
            samples = build_pause_segment(segment["duration_sec"], segment["noise_level"], seed=20260528 + index)

        start_sec = cursor
        end_sec = cursor + segment["duration_sec"]
        metadata.append(
            {
                "label": segment["label"],
                "kind": segment["kind"],
                "start_sec": start_sec,
                "end_sec": end_sec,
                "duration_sec": segment["duration_sec"],
                "bpm": segment.get("bpm"),
                "expected_detection": segment["kind"] == "tempo",
            }
        )
        parts.append(samples)
        cursor = end_sec

    audio = np.concatenate(parts).astype(np.float32)
    peak = float(np.max(np.abs(audio))) if audio.size else 1.0
    if peak > 0:
        audio = 0.92 * (audio / peak)
    return audio, metadata


def encode_mp3(ffmpeg_exe: Path, wav_path: Path, mp3_path: Path) -> None:
    command = [
        str(ffmpeg_exe),
        "-y",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(mp3_path),
    ]
    subprocess.run(command, check=True)


def build_payload(preset_name: str, preset: dict, metadata: list[dict]) -> dict:
    segments = preset["segments"]
    return {
        "preset": preset_name,
        "description": preset["description"],
        "sample_rate": SAMPLE_RATE,
        "total_duration_sec": sum(segment["duration_sec"] for segment in segments),
        "segments": metadata,
        "notes": preset["notes"],
    }


def build_manifest_entry(output_dir: Path, base_name: str, preset_name: str, payload: dict) -> dict:
    return {
        "base_name": base_name,
        "preset": preset_name,
        "description": payload["description"],
        "duration_sec": payload["total_duration_sec"],
        "sample_rate": payload["sample_rate"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mp3": str((output_dir / f"{base_name}.mp3").resolve()),
        "wav": str((output_dir / f"{base_name}.wav").resolve()),
        "ground_truth": str((output_dir / f"{base_name}.json").resolve()),
    }


def generate_assets(output_dir: Path, ffmpeg_exe: Path, preset_name: str, output_name: str | None = None) -> dict:
    preset = PRESETS[preset_name]
    base_name = sanitize_base_name(output_name or preset["base_name"])
    wav_path = output_dir / f"{base_name}.wav"
    mp3_path = output_dir / f"{base_name}.mp3"
    json_path = output_dir / f"{base_name}.json"

    audio, metadata = assemble_reference_audio(preset["segments"])
    payload = build_payload(preset_name, preset, metadata)

    sf.write(wav_path, audio, SAMPLE_RATE)
    encode_mp3(ffmpeg_exe, wav_path, mp3_path)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    entry = build_manifest_entry(output_dir, base_name, preset_name, payload)
    upsert_manifest_entry(output_dir / MANIFEST_NAME, entry)
    return entry


def print_manifest(manifest_path: Path) -> None:
    files = load_manifest(manifest_path)
    if not files:
        print("No generated calibration files found.")
        return

    for item in sorted(files, key=lambda current: current["base_name"]):
        print(f"{item['base_name']} | preset={item['preset']} | duration={item['duration_sec']}s | mp3={item['mp3']}")


def generate_prebuilt_library(output_dir: Path, ffmpeg_exe: Path) -> list[dict]:
    entries = []
    for preset_name in PRESETS:
        entries.append(generate_assets(output_dir, ffmpeg_exe, preset_name))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate calibration MP3 samples and track them in a manifest.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for generated assets.")
    parser.add_argument("--ffmpeg", help="Absolute path to ffmpeg.exe.")
    parser.add_argument("--preset", default="generic_reference", choices=sorted(PRESETS.keys()), help="Which preset to generate.")
    parser.add_argument("--name", help="Optional output base name. Example: my_test_sample")
    parser.add_argument("--list", action="store_true", help="Show the current list of generated calibration files.")
    parser.add_argument("--generate-library", action="store_true", help="Generate every built-in preset and refresh the manifest.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_NAME

    if args.list:
        print_manifest(manifest_path)
        return

    if not args.ffmpeg:
        parser.error("--ffmpeg is required unless --list is used.")

    ffmpeg_exe = Path(args.ffmpeg)
    if args.generate_library:
        entries = generate_prebuilt_library(output_dir, ffmpeg_exe)
        for entry in entries:
            print(f"Generated: {entry['mp3']}")
        print(f"Manifest: {manifest_path}")
        return

    entry = generate_assets(output_dir, ffmpeg_exe, args.preset, args.name)
    print(f"WAV: {entry['wav']}")
    print(f"MP3: {entry['mp3']}")
    print(f"JSON: {entry['ground_truth']}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
