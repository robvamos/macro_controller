"""Recover interrupted GUI learning sessions without mutating the macro database."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from PIL import Image

from core.paths import DB_PATH, RECOVERED_LEARNING_SESSIONS_DIR
from services.shared_knowledge_export_service import parse_game_element_description, slugify


DEFAULT_MACRO_DB = DB_PATH
DEFAULT_RECOVERY_ROOT = RECOVERED_LEARNING_SESSIONS_DIR


def recover_learning_session(
    session_name: str,
    *,
    db_path: str | Path = DEFAULT_MACRO_DB,
    output_root: str | Path = DEFAULT_RECOVERY_ROOT,
    declared_workflow_id: str | None = None,
    objective: str | None = None,
) -> dict[str, Any]:
    """Rebuild ordered click evidence from metadata using an immutable SQLite connection."""
    source_path = Path(db_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    rows = _read_game_elements_immutable(source_path)
    candidates = _collect_session_events(rows, session_name)
    events = _validate_and_order(candidates)
    if not events:
        raise ValueError(f"No recoverable events found for session: {session_name}")

    session_slug = _session_slug(session_name)
    target_root = Path(output_root)
    image_dir = target_root / session_slug
    image_dir.mkdir(parents=True, exist_ok=True)
    exported_images = _export_event_images(events, image_dir)

    recovered_at = datetime.now(timezone.utc).isoformat()
    click_sequence = []
    for event, evidence in zip(events, exported_images, strict=True):
        auto = event["auto"]
        note = event["note"]
        normalized = auto.get("normalized_position") or note.get("normalized_position") or {}
        click = auto.get("click_position") or {}
        click_sequence.append(
            {
                "sequence_index": event["sequence_index"],
                "time": auto.get("event_time_ms"),
                "type": "mouse",
                "event": "down",
                "button": auto.get("button", "left"),
                "x": click.get("x"),
                "y": click.get("y"),
                "normalized_x": normalized.get("x"),
                "normalized_y": normalized.get("y"),
                "game_element_id": event["element_id"],
                "previous_game_element_id": note.get("previous_element_id"),
                "ui_graph_id": auto.get("graph_id"),
                "ui_node_id": note.get("semantic_node_id") or note.get("view_node_id"),
                "screen_zone": note.get("screen_zone"),
                "evidence": evidence,
                "semantic_status": "observed_unlabeled",
                "automation_allowed": False,
            }
        )

    payload = {
        "schema": "doomsday.learning.recovered_session.v1",
        "macro_id": None,
        "name": session_name,
        "description": objective or "Sessione GUI interrotta recuperata dai metadati degli elementi.",
        "system_key": "recovered_general_click_elements_learning",
        "system_payload": {
            "recovered_from_element_metadata": True,
            "source_database": source_path.name,
            "source_open_mode": "read_only_immutable",
            "declared_workflow_id": declared_workflow_id,
            "semantic_policy": "no_label_from_coordinates_only",
            "full_frames_available": False,
            "click_crop_limitations": (
                "I crop mostrano il contesto del click ma non dimostrano da soli lo stato della schermata."
            ),
        },
        "created_at": None,
        "updated_at": recovered_at,
        "recovery_status": "complete_with_click_crops_only",
        "click_sequence": click_sequence,
    }
    target_path = target_root / f"{session_slug}.json"
    _atomic_write_json(target_path, payload)
    return {
        "path": str(target_path.resolve()),
        "session_name": session_name,
        "click_count": len(click_sequence),
        "image_count": sum(1 for item in exported_images if item.get("image_path")),
        "payload": payload,
    }


def load_recovered_learning_sessions(root: str | Path) -> list[dict[str, Any]]:
    """Load supplemental sessions, ignoring unrelated JSON files deterministically."""
    base = Path(root)
    if not base.exists():
        return []
    sessions = []
    for path in sorted(base.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != "doomsday.learning.recovered_session.v1":
            continue
        sessions.append(payload)
    return sessions


def _read_game_elements_immutable(db_path: Path) -> list[dict[str, Any]]:
    uri = db_path.as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT id, nome, descrizione, immagine, formato_immagine FROM GameElements ORDER BY id"
            )
        ]
    finally:
        connection.close()


def _collect_session_events(rows: list[dict[str, Any]], session_name: str) -> list[dict[str, Any]]:
    events = []
    for row in rows:
        parsed = parse_game_element_description(row.get("descrizione"))
        metadata = parsed.get("metadata_blocks") or {}
        notes = [
            item
            for item in metadata.get("general_click_semantic_note", [])
            if isinstance(item, dict) and item.get("session_name") == session_name
        ]
        autos = [
            item
            for item in metadata.get("auto_click_element_metadata", [])
            if isinstance(item, dict) and item.get("macro_name") == session_name
        ]
        autos_by_sequence = {int(item["sequence_index"]): item for item in autos if item.get("sequence_index") is not None}
        for note in notes:
            sequence_index = int(note["sequence_index"])
            auto = autos_by_sequence.get(sequence_index)
            if auto is None:
                raise ValueError(f"Missing AUTO metadata for sequence {sequence_index}, element {row['id']}")
            events.append(
                {
                    "sequence_index": sequence_index,
                    "element_id": int(row["id"]),
                    "element_name": row["nome"],
                    "image_blob": row["immagine"],
                    "image_format": row["formato_immagine"],
                    "note": note,
                    "auto": auto,
                }
            )
    return events


def _validate_and_order(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(events, key=lambda item: item["sequence_index"])
    indices = [item["sequence_index"] for item in ordered]
    if indices != list(range(1, len(ordered) + 1)):
        raise ValueError(f"Learning sequence is not contiguous: {indices}")
    previous_id = None
    for event in ordered:
        recorded_previous = event["note"].get("previous_element_id")
        if recorded_previous != previous_id:
            raise ValueError(
                f"Broken predecessor at sequence {event['sequence_index']}: "
                f"expected {previous_id}, found {recorded_previous}"
            )
        previous_id = event["element_id"]
    return ordered


def _export_event_images(events: list[dict[str, Any]], image_dir: Path) -> list[dict[str, Any]]:
    records = []
    for event in events:
        blob = bytes(event["image_blob"])
        with Image.open(BytesIO(blob)) as source:
            source.load()
            image = source.convert("RGB")
        filename = f"{event['sequence_index']:04d}_element_{event['element_id']:04d}.png"
        path = image_dir / filename
        image.save(path, format="PNG")
        digest = sha256(path.read_bytes()).hexdigest()
        records.append(
            {
                "kind": "click_crop",
                "image_path": f"{image_dir.name}/{filename}",
                "sha256": digest,
                "width": image.width,
                "height": image.height,
                "visual_scope": "local_click_context_only",
                "semantic_gap": (
                    "shared_spatial_placeholder"
                    if event["auto"].get("source") == "macro_recording_semantic_click_action"
                    else None
                ),
            }
        )
        image.close()
    return records


def _session_slug(session_name: str) -> str:
    timestamp = session_name.rsplit(" - ", 1)[-1]
    if re.fullmatch(r"\d{8}_\d{6}", timestamp):
        return timestamp
    return slugify(session_name)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


__all__ = [
    "DEFAULT_MACRO_DB",
    "DEFAULT_RECOVERY_ROOT",
    "load_recovered_learning_sessions",
    "recover_learning_session",
]
