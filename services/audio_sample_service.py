from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf


SAMPLE_RATE = 44_100
DEFAULT_OUTPUT_DIR = Path("data/calibration")
MANIFEST_NAME = "index.json"
DEFAULT_IMPORTED_PRESET = "uploaded_selection"
KNOWN_FFMPEG_PATH = Path(r"F:\_CODEX\Audio2VideoPal\.tools\ffmpeg\bin\ffmpeg.exe")


def sanitize_base_name(name: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in {"_", "-"} else "_" for character in name.strip())
    cleaned = cleaned.strip("_")
    if not cleaned:
        raise ValueError("Il nome del campione deve contenere almeno un carattere valido.")
    return cleaned


def load_manifest(manifest_path: Path) -> list[dict]:
    if not manifest_path.exists():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return payload.get("files", [])


def save_manifest(manifest_path: Path, files: list[dict]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": sorted(files, key=lambda item: item["base_name"]),
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def upsert_manifest_entry(manifest_path: Path, entry: dict) -> None:
    files = [item for item in load_manifest(manifest_path) if item["base_name"] != entry["base_name"]]
    files.append(entry)
    save_manifest(manifest_path, files)


def list_audio_samples(output_dir: Path | None = None) -> list[dict]:
    manifest_path = Path(output_dir or DEFAULT_OUTPUT_DIR) / MANIFEST_NAME
    return load_manifest(manifest_path)


def get_audio_sample_entry(base_name: str, output_dir: Path | None = None) -> dict | None:
    for entry in list_audio_samples(output_dir):
        if entry["base_name"] == base_name:
            return entry
    return None


def resolve_ffmpeg_executable(ffmpeg_exe: str | Path | None = None) -> Path:
    candidates = [
        Path(ffmpeg_exe) if ffmpeg_exe else None,
        Path(os.environ["FFMPEG_EXE"]) if os.environ.get("FFMPEG_EXE") else None,
        KNOWN_FFMPEG_PATH,
        Path(shutil.which("ffmpeg")) if shutil.which("ffmpeg") else None,
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise FileNotFoundError("ffmpeg non trovato. Configura FFMPEG_EXE o installa ffmpeg.")


def resolve_ffprobe_executable(ffmpeg_path: str | Path | None = None) -> Path | None:
    ffmpeg_candidate = Path(ffmpeg_path) if ffmpeg_path else None
    sibling = ffmpeg_candidate.with_name("ffprobe.exe") if ffmpeg_candidate else None
    candidates = [
        sibling,
        KNOWN_FFMPEG_PATH.with_name("ffprobe.exe"),
        Path(shutil.which("ffprobe")) if shutil.which("ffprobe") else None,
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None


def get_audio_duration_seconds(source_path: str | Path, ffprobe_path: str | Path | None = None) -> float:
    source = Path(source_path)
    try:
        info = sf.info(str(source))
        return float(info.duration)
    except RuntimeError:
        ffprobe = resolve_ffprobe_executable(ffprobe_path)
        if ffprobe is None:
            raise ValueError(f"Impossibile leggere la durata audio di {source}.")
        command = [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(source),
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return float(result.stdout.strip())


def validate_time_selection(start_sec: float, end_sec: float, total_duration_sec: float) -> None:
    if start_sec < 0:
        raise ValueError("L'inizio del campione non puo' essere negativo.")
    if end_sec <= start_sec:
        raise ValueError("La fine del campione deve essere maggiore dell'inizio.")
    if end_sec > total_duration_sec:
        raise ValueError("La selezione supera la durata del file audio.")


def _normalize_to_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio.astype(np.float32)
    return np.mean(audio, axis=1, dtype=np.float32)


def _resample_audio(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return audio.astype(np.float32)
    duration_sec = len(audio) / float(source_rate)
    target_samples = max(1, int(round(duration_sec * target_rate)))
    source_positions = np.linspace(0.0, duration_sec, num=len(audio), endpoint=False)
    target_positions = np.linspace(0.0, duration_sec, num=target_samples, endpoint=False)
    return np.interp(target_positions, source_positions, audio).astype(np.float32)


def _extract_selection_with_soundfile(source_path: Path, start_sec: float, end_sec: float) -> np.ndarray:
    info = sf.info(str(source_path))
    start_frame = int(start_sec * info.samplerate)
    stop_frame = int(end_sec * info.samplerate)
    audio, sample_rate = sf.read(str(source_path), start=start_frame, stop=stop_frame, always_2d=False)
    mono_audio = _normalize_to_mono(np.asarray(audio, dtype=np.float32))
    return _resample_audio(mono_audio, int(sample_rate), SAMPLE_RATE)


def load_audio_array(source_path: str | Path) -> np.ndarray:
    audio, sample_rate = sf.read(str(source_path), always_2d=False)
    mono_audio = _normalize_to_mono(np.asarray(audio, dtype=np.float32))
    return _resample_audio(mono_audio, int(sample_rate), SAMPLE_RATE)


def slice_audio_array(audio: np.ndarray, start_sec: float, end_sec: float) -> np.ndarray:
    start_frame = max(0, int(round(start_sec * SAMPLE_RATE)))
    end_frame = min(len(audio), int(round(end_sec * SAMPLE_RATE)))
    return np.asarray(audio[start_frame:end_frame], dtype=np.float32)


def _export_selection_to_wav_with_ffmpeg(
    ffmpeg_exe: Path,
    source_path: Path,
    wav_path: Path,
    start_sec: float,
    end_sec: float,
) -> None:
    command = [
        str(ffmpeg_exe),
        "-y",
        "-ss",
        f"{start_sec:.3f}",
        "-to",
        f"{end_sec:.3f}",
        "-i",
        str(source_path),
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        str(wav_path),
    ]
    subprocess.run(command, check=True)


def encode_wav_to_mp3(ffmpeg_exe: Path, wav_path: Path, mp3_path: Path) -> None:
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


def load_sample_payload(base_name: str, output_dir: Path | None = None) -> dict:
    selected_output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    json_path = selected_output_dir / f"{base_name}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Ground truth non trovato per il campione {base_name}.")
    return json.loads(json_path.read_text(encoding="utf-8"))


def load_sample_audio(base_name: str, output_dir: Path | None = None) -> np.ndarray:
    selected_output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    wav_path = selected_output_dir / f"{base_name}.wav"
    if wav_path.exists():
        return load_audio_array(wav_path)

    entry = get_audio_sample_entry(base_name, selected_output_dir)
    if entry and entry.get("mp3"):
        mp3_path = Path(entry["mp3"])
        if mp3_path.exists():
            return load_audio_array(mp3_path)
    raise FileNotFoundError(f"Audio non trovato per il campione {base_name}.")


def write_sample_assets(
    *,
    audio: np.ndarray,
    base_name: str,
    payload: dict,
    output_dir: Path | None = None,
    ffmpeg_exe: str | Path | None = None,
) -> dict:
    selected_output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    selected_output_dir.mkdir(parents=True, exist_ok=True)

    wav_path = selected_output_dir / f"{base_name}.wav"
    mp3_path = selected_output_dir / f"{base_name}.mp3"
    json_path = selected_output_dir / f"{base_name}.json"

    sf.write(wav_path, np.asarray(audio, dtype=np.float32), SAMPLE_RATE)
    ffmpeg_path = resolve_ffmpeg_executable(ffmpeg_exe)
    encode_wav_to_mp3(ffmpeg_path, wav_path, mp3_path)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    entry = build_manifest_entry(selected_output_dir, base_name, payload)
    upsert_manifest_entry(selected_output_dir / MANIFEST_NAME, entry)
    return entry


def build_imported_sample_payload(
    *,
    source_path: Path,
    base_name: str,
    start_sec: float,
    end_sec: float,
    source_duration_sec: float,
) -> dict:
    return {
        "preset": DEFAULT_IMPORTED_PRESET,
        "description": "Sample extracted from a user-selected audio section.",
        "sample_rate": SAMPLE_RATE,
        "total_duration_sec": round(end_sec - start_sec, 3),
        "segments": [
            {
                "label": "selected_section",
                "kind": "imported_audio",
                "start_sec": 0.0,
                "end_sec": round(end_sec - start_sec, 3),
                "duration_sec": round(end_sec - start_sec, 3),
                "bpm": None,
                "expected_detection": None,
            }
        ],
        "notes": {
            "purpose": "User-defined calibration sample extracted from an uploaded audio file.",
            "source_file": str(source_path.resolve()),
            "source_duration_sec": round(source_duration_sec, 3),
            "selection_start_sec": round(start_sec, 3),
            "selection_end_sec": round(end_sec, 3),
            "output_name": base_name,
        },
    }


def build_manifest_entry(output_dir: Path, base_name: str, payload: dict) -> dict:
    notes = payload.get("notes", {})
    return {
        "base_name": base_name,
        "preset": payload["preset"],
        "description": payload["description"],
        "duration_sec": payload["total_duration_sec"],
        "sample_rate": payload["sample_rate"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mp3": str((output_dir / f"{base_name}.mp3").resolve()),
        "wav": str((output_dir / f"{base_name}.wav").resolve()),
        "ground_truth": str((output_dir / f"{base_name}.json").resolve()),
        "source_file": notes.get("source_file"),
        "selection_start_sec": notes.get("selection_start_sec"),
        "selection_end_sec": notes.get("selection_end_sec"),
        "source_sample": notes.get("source_sample"),
        "component_samples": notes.get("component_samples"),
    }


def create_audio_sample_from_selection(
    *,
    source_path: str | Path,
    output_name: str,
    start_sec: float,
    end_sec: float,
    output_dir: str | Path | None = None,
    ffmpeg_exe: str | Path | None = None,
) -> dict:
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"File audio non trovato: {source}")

    selected_output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    selected_output_dir.mkdir(parents=True, exist_ok=True)

    total_duration = get_audio_duration_seconds(source, ffprobe_path=ffmpeg_exe)
    validate_time_selection(start_sec, end_sec, total_duration)

    base_name = sanitize_base_name(output_name)
    wav_path = selected_output_dir / f"{base_name}.wav"
    mp3_path = selected_output_dir / f"{base_name}.mp3"
    json_path = selected_output_dir / f"{base_name}.json"

    try:
        audio = _extract_selection_with_soundfile(source, start_sec, end_sec)
        sf.write(wav_path, audio, SAMPLE_RATE)
    except RuntimeError:
        ffmpeg_path = resolve_ffmpeg_executable(ffmpeg_exe)
        _export_selection_to_wav_with_ffmpeg(ffmpeg_path, source, wav_path, start_sec, end_sec)
    else:
        ffmpeg_path = resolve_ffmpeg_executable(ffmpeg_exe)

    encode_wav_to_mp3(ffmpeg_path, wav_path, mp3_path)

    payload = build_imported_sample_payload(
        source_path=source,
        base_name=base_name,
        start_sec=start_sec,
        end_sec=end_sec,
        source_duration_sec=total_duration,
    )
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    entry = build_manifest_entry(selected_output_dir, base_name, payload)
    upsert_manifest_entry(selected_output_dir / MANIFEST_NAME, entry)
    return entry


def split_audio_sample(
    *,
    base_name: str,
    output_dir: str | Path | None = None,
    ffmpeg_exe: str | Path | None = None,
) -> list[dict]:
    payload = load_sample_payload(base_name, output_dir)
    source_audio = load_sample_audio(base_name, output_dir)
    segments = payload.get("segments") or []
    if not segments:
        raise ValueError(f"Il campione {base_name} non ha segmenti da scomporre.")

    entries = []
    for index, segment in enumerate(segments, start=1):
        segment_base_name = sanitize_base_name(f"{base_name}_{index:02d}_{segment['label']}")
        segment_audio = slice_audio_array(source_audio, float(segment["start_sec"]), float(segment["end_sec"]))
        segment_duration = round(float(segment["end_sec"]) - float(segment["start_sec"]), 3)
        segment_payload = {
            "preset": "derived_segment",
            "description": f"Segmento derivato da {base_name}: {segment['label']}",
            "sample_rate": SAMPLE_RATE,
            "total_duration_sec": segment_duration,
            "segments": [
                {
                    "label": segment["label"],
                    "kind": segment.get("kind"),
                    "start_sec": 0.0,
                    "end_sec": segment_duration,
                    "duration_sec": segment_duration,
                    "bpm": segment.get("bpm"),
                    "expected_detection": segment.get("expected_detection"),
                }
            ],
            "notes": {
                "purpose": "Derived segment for beat-phase and order testing.",
                "source_sample": base_name,
                "source_segment_label": segment["label"],
                "source_segment_index": index,
                "original_start_sec": segment["start_sec"],
                "original_end_sec": segment["end_sec"],
            },
        }
        entry = write_sample_assets(
            audio=segment_audio,
            base_name=segment_base_name,
            payload=segment_payload,
            output_dir=output_dir,
            ffmpeg_exe=ffmpeg_exe,
        )
        entries.append(entry)
    return entries


def compose_test_song(
    *,
    sample_names: list[str],
    output_name: str,
    output_dir: str | Path | None = None,
    ffmpeg_exe: str | Path | None = None,
    gap_sec: float = 0.0,
    learning_objective: str | None = None,
) -> dict:
    if not sample_names:
        raise ValueError("Seleziona almeno un campione da combinare.")
    if gap_sec < 0:
        raise ValueError("Il gap tra campioni non puo' essere negativo.")

    base_name = sanitize_base_name(output_name)
    gap_audio = np.zeros(int(round(gap_sec * SAMPLE_RATE)), dtype=np.float32) if gap_sec > 0 else None

    combined_parts = []
    combined_segments = []
    cursor = 0.0

    for sample_name in sample_names:
        sample_payload = load_sample_payload(sample_name, output_dir)
        sample_audio = load_sample_audio(sample_name, output_dir)
        sample_duration = round(len(sample_audio) / SAMPLE_RATE, 3)
        combined_parts.append(sample_audio)

        source_segments = sample_payload.get("segments") or [
            {
                "label": sample_name,
                "kind": "composed_block",
                "start_sec": 0.0,
                "end_sec": sample_duration,
                "duration_sec": sample_duration,
                "bpm": None,
                "expected_detection": None,
            }
        ]

        for segment in source_segments:
            duration_sec = round(float(segment["end_sec"]) - float(segment["start_sec"]), 3)
            combined_segments.append(
                {
                    "label": f"{sample_name}:{segment['label']}",
                    "kind": segment.get("kind"),
                    "start_sec": round(cursor, 3),
                    "end_sec": round(cursor + duration_sec, 3),
                    "duration_sec": duration_sec,
                    "bpm": segment.get("bpm"),
                    "expected_detection": segment.get("expected_detection"),
                    "source_sample": sample_name,
                }
            )
            cursor += duration_sec

        if gap_audio is not None and sample_name != sample_names[-1]:
            combined_parts.append(gap_audio)
            combined_segments.append(
                {
                    "label": f"{sample_name}:gap",
                    "kind": "pause",
                    "start_sec": round(cursor, 3),
                    "end_sec": round(cursor + gap_sec, 3),
                    "duration_sec": round(gap_sec, 3),
                    "bpm": None,
                    "expected_detection": False,
                    "source_sample": sample_name,
                }
            )
            cursor += gap_sec

    combined_audio = np.concatenate(combined_parts).astype(np.float32)
    payload = {
        "preset": "composed_test_song",
        "description": "Test song composed from selected samples for beat, phase, and quarter-order evaluation.",
        "sample_rate": SAMPLE_RATE,
        "total_duration_sec": round(len(combined_audio) / SAMPLE_RATE, 3),
        "segments": combined_segments,
        "notes": {
            "purpose": "Composite test song for predictive learning windows and beat-one recognition.",
            "component_samples": sample_names,
            "gap_sec": round(gap_sec, 3),
            "learning_objective": learning_objective
            or "Recognize tempo, bar phase, quarter ordering, and identify beat one.",
        },
    }
    return write_sample_assets(
        audio=combined_audio,
        base_name=base_name,
        payload=payload,
        output_dir=output_dir,
        ffmpeg_exe=ffmpeg_exe,
    )
