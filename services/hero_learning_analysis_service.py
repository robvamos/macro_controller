"""Turn full-frame hero-learning evidence into labeled screen observations."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from doomsday.ocr.engine import OcrEngine, TesseractCliEngine
from doomsday.vision.hero_screen_classifier import classify_hero_screen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "doomsday" / "knowledge" / "hero_learning_observations"


def analyze_hero_learning_session(
    session_dir: str | Path,
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    engine: OcrEngine | None = None,
) -> dict[str, Any]:
    base = Path(session_dir)
    session = json.loads((base / "session.json").read_text(encoding="utf-8"))
    if session.get("declared_workflow_id") != "hero-inspection-v1":
        raise ValueError("Session is not declared as hero-inspection-v1")
    frames = _load_jsonl(base / "frames.jsonl")
    events = {int(item["sequence_index"]): item for item in _load_jsonl(base / "events.jsonl")}
    selected_frames = _select_after_frames(frames)
    ocr_engine = engine or TesseractCliEngine()

    observations = []
    for frame in selected_frames:
        image_path = Path(frame["path"])
        with Image.open(image_path) as source:
            source.load()
            half = source.resize((max(1, source.width // 2), max(1, source.height // 2)))
            prepared = ImageOps.autocontrast(ImageOps.grayscale(half))
        result = ocr_engine.recognize(prepared, language="ita+eng", page_segmentation_mode=11)
        prepared.close()
        classification = classify_hero_screen(result.text)
        sequence_index = int(frame["sequence_index"])
        event = events.get(sequence_index, {})
        observations.append(
            {
                "sequence_index": sequence_index,
                "event_time_ms": frame.get("event_time_ms"),
                "game_element_id": event.get("game_element_id"),
                "normalized_click": frame.get("normalized_click"),
                "frame_path": image_path.resolve().as_posix(),
                "frame_sha256": frame.get("sha256"),
                "frame_quality": frame.get("quality"),
                "phase": frame.get("phase", "after_stabilization"),
                "ocr": {
                    "text": result.text,
                    "mean_confidence": result.mean_confidence,
                    "language": result.language,
                    "engine": result.engine,
                },
                "screen": asdict(classification),
                "transition_binding_status": "observed_unlabeled",
                "automation_allowed": False,
            }
        )

    timestamp = session["session_name"].rsplit(" - ", 1)[-1]
    payload = {
        "schema": "doomsday.hero_learning_observations.v1",
        "workflow_id": "hero-inspection-v1",
        "session_name": session["session_name"],
        "source_session_status": session.get("status"),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "semantic_policy": "screen labels from OCR anchors; click actions remain unlabeled",
        "observation_count": len(observations),
        "observations": observations,
    }
    output = Path(output_root) / f"{timestamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)
    return {"path": str(output.resolve()), "payload": payload}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _select_after_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sequence: dict[int, dict[str, Any]] = {}
    for frame in frames:
        sequence_index = int(frame["sequence_index"])
        phase = frame.get("phase", "after_stabilization")
        if phase == "after_stabilization" or sequence_index not in by_sequence:
            by_sequence[sequence_index] = frame
    return [by_sequence[index] for index in sorted(by_sequence)]


__all__ = ["DEFAULT_OUTPUT_ROOT", "analyze_hero_learning_session"]
