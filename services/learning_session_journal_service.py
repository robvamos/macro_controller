"""Crash-safe JSONL journal for supervised GUI learning sessions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEARNING_SESSIONS_ROOT = PROJECT_ROOT / ".tools" / "learning_sessions"


def learning_session_directory(
    session_name: str,
    *,
    root: str | Path = DEFAULT_LEARNING_SESSIONS_ROOT,
) -> Path:
    return Path(root) / _slug(session_name)


def initialize_learning_session_journal(
    *,
    session_name: str,
    scenario: str,
    objective: str,
    declared_workflow_id: str | None,
    window_rect: tuple[int, int, int, int] | None,
    root: str | Path = DEFAULT_LEARNING_SESSIONS_ROOT,
) -> Path:
    """Create the durable session manifest before the first click is observed."""
    session_dir = learning_session_directory(session_name, root=root)
    session_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "doomsday.learning.session.v1",
        "session_name": session_name,
        "scenario": scenario,
        "objective": objective,
        "declared_workflow_id": declared_workflow_id,
        "semantic_policy": "labels_require_visual_validation",
        "status": "recording",
        "started_at": _utc_now(),
        "window_rect": _rect_to_dict(window_rect),
        "event_journal": "events.jsonl",
        "frame_journal": "frames.jsonl",
    }
    _atomic_write_json(session_dir / "session.json", payload)
    return session_dir


def append_learning_event(
    *,
    session_name: str,
    event: dict[str, Any],
    root: str | Path = DEFAULT_LEARNING_SESSIONS_ROOT,
) -> Path:
    """Append one self-contained event so an interrupted session remains recoverable."""
    session_dir = learning_session_directory(session_name, root=root)
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / "events.jsonl"
    payload = {
        "schema": "doomsday.learning.event.v1",
        "session_name": session_name,
        "recorded_at": _utc_now(),
        **event,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
    return path


def finalize_learning_session_journal(
    *,
    session_name: str,
    status: str,
    click_count: int,
    macro_id: int | None = None,
    root: str | Path = DEFAULT_LEARNING_SESSIONS_ROOT,
) -> Path:
    if status not in {"completed", "empty", "failed"}:
        raise ValueError(f"Unsupported learning-session status: {status}")
    session_dir = learning_session_directory(session_name, root=root)
    manifest = session_dir / "session.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload.update(
        {
            "status": status,
            "ended_at": _utc_now(),
            "click_count": int(click_count),
            "macro_id": macro_id,
        }
    )
    _atomic_write_json(manifest, payload)
    return manifest


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", value.casefold()).strip("-")[:120] or "session"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rect_to_dict(rect: tuple[int, int, int, int] | None) -> dict[str, int] | None:
    if rect is None:
        return None
    left, top, right, bottom = rect
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


__all__ = [
    "DEFAULT_LEARNING_SESSIONS_ROOT",
    "append_learning_event",
    "finalize_learning_session_journal",
    "initialize_learning_session_journal",
    "learning_session_directory",
]
