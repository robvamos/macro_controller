"""Frame completi post-click per le sessioni di learning Doomsday."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from core.paths import LEARNING_SESSIONS_DIR
from doomsday.vision.desktop_capture import assess_frame_quality, capture_screen_region


DEFAULT_LEARNING_FRAMES_ROOT = LEARNING_SESSIONS_DIR


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", value.casefold()).strip("-")[:120] or "session"


def capture_learning_frame(
    *,
    session_name: str,
    sequence_index: int,
    window_rect: tuple[int, int, int, int],
    event_time_ms: int,
    view_node_id: str,
    semantic_node_id: str,
    normalized_x: float,
    normalized_y: float,
    phase: str = "after_stabilization",
    root: str | Path = DEFAULT_LEARNING_FRAMES_ROOT,
) -> dict:
    """Salva PNG e metadata JSONL; un frame incompleto viene marcato, non nascosto."""
    left, top, right, bottom = window_rect
    image = capture_screen_region(left, top, right, bottom)
    quality = assess_frame_quality(image)
    session_dir = Path(root) / _slug(session_name)
    session_dir.mkdir(parents=True, exist_ok=True)
    if phase not in {"click_time", "after_stabilization"}:
        raise ValueError(f"Unsupported learning frame phase: {phase}")
    path = session_dir / f"{sequence_index:04d}-{phase}-{event_time_ms:09d}ms.png"
    image.save(path, format="PNG")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {
        "schema": "doomsday.learning.frame.v1",
        "session_name": session_name,
        "sequence_index": sequence_index,
        "event_time_ms": event_time_ms,
        "phase": phase,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "path": path.resolve().as_posix(),
        "sha256": digest,
        "width": image.width,
        "height": image.height,
        "view_node_id": view_node_id,
        "semantic_node_id": semantic_node_id,
        "normalized_click": {"x": normalized_x, "y": normalized_y},
        "quality": asdict(quality),
    }
    manifest = session_dir / "frames.jsonl"
    with manifest.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return payload


__all__ = ["DEFAULT_LEARNING_FRAMES_ROOT", "capture_learning_frame"]
