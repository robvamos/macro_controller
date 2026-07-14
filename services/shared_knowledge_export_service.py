"""Export shared Doomsday learning knowledge into versionable files."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from doomsday.vision.ui_graph import build_default_doomsday_ui_graph
from game_elements import blob_to_image
from repositories.game_element_repository import get_all_game_elements, get_game_element_by_id
from repositories.macro_repository import get_all_macros, load_macro_events
from services.learning_pattern_service import LEARNING_SYSTEM_KEYS, suggest_repeated_learning_patterns


SHARED_KNOWLEDGE_DIR = Path("data/doomsday/knowledge")
GAME_ELEMENT_IMAGE_DIR_NAME = "game_elements"
METADATA_MARKERS = (
    "AUTO_CLICK_ELEMENT_METADATA:",
    "GENERAL_CLICK_SEMANTIC_NOTE:",
)
SHARED_MACRO_SYSTEM_KEYS = LEARNING_SYSTEM_KEYS | {"launch_game"}


def export_shared_knowledge(output_dir: Path | str = SHARED_KNOWLEDGE_DIR) -> dict[str, Any]:
    """Write the common learning graph, element catalog and pattern hints to disk."""
    target_dir = Path(output_dir)
    image_dir = target_dir / GAME_ELEMENT_IMAGE_DIR_NAME
    image_dir.mkdir(parents=True, exist_ok=True)

    element_records = _export_game_elements(target_dir, image_dir)
    sessions = _collect_learning_sessions(target_dir / "recovered_learning_sessions")
    ui_graph = _serialize_default_ui_graph()
    patterns = _collect_pattern_suggestions()

    _write_json(target_dir / "game_elements_manifest.json", {"game_elements": element_records})
    _write_json(target_dir / "learning_sessions.json", {"learning_sessions": sessions})
    _write_json(target_dir / "ui_semantic_graph.json", ui_graph)
    _write_json(target_dir / "pattern_suggestions.json", {"pattern_suggestions": patterns})

    return {
        "output_dir": str(target_dir),
        "game_elements": len(element_records),
        "learning_sessions": len(sessions),
        "ui_nodes": len(ui_graph["nodes"]),
        "ui_edges": len(ui_graph["edges"]),
        "pattern_suggestions": len(patterns),
    }


def parse_game_element_description(description: str | None) -> dict[str, Any]:
    """Extract machine-readable metadata embedded in human descriptions."""
    raw_description = description or ""
    metadata_blocks: dict[str, list[Any]] = {}
    decoder = json.JSONDecoder()

    for marker in METADATA_MARKERS:
        search_start = 0
        marker_key = marker.rstrip(":").lower()
        while True:
            marker_index = raw_description.find(marker, search_start)
            if marker_index < 0:
                break
            json_start = marker_index + len(marker)
            while json_start < len(raw_description) and raw_description[json_start].isspace():
                json_start += 1
            try:
                block, offset = decoder.raw_decode(raw_description[json_start:])
            except json.JSONDecodeError:
                search_start = marker_index + len(marker)
                continue
            metadata_blocks.setdefault(marker_key, []).append(block)
            search_start = json_start + offset

    semantic_hint = ""
    hint_match = re.search(r"\[semantic_hint\]\s*(.+)", raw_description)
    if hint_match:
        semantic_hint = hint_match.group(1).strip()

    memory_note = ""
    memory_marker = "MEMORIA SEMANTICA:"
    if memory_marker in raw_description:
        memory_note = raw_description.split(memory_marker, 1)[1].strip()

    return {
        "metadata_blocks": metadata_blocks,
        "semantic_hint": semantic_hint,
        "memory_note": memory_note,
        "plain_description": _strip_embedded_metadata(raw_description),
    }


def slugify(value: str) -> str:
    """Return a filesystem-stable ASCII slug."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value or "element").strip("_").lower()
    return normalized or "element"


def _export_game_elements(target_dir: Path, image_dir: Path) -> list[dict[str, Any]]:
    records = []
    elements = sorted(get_all_game_elements(), key=lambda item: int(item["id"]))

    for element in elements:
        full_element = get_game_element_by_id(element["id"]) or element
        image_relative_path = None
        image_size = None
        image_blob = full_element.get("immagine")
        if image_blob:
            image = blob_to_image(image_blob, full_element.get("formato_immagine") or "PNG")
            image_size = {"width": image.width, "height": image.height}
            image_name = f"{int(element['id']):04d}_{slugify(element.get('nome') or '')}.png"
            image_path = image_dir / image_name
            image.save(image_path, format="PNG")
            image_relative_path = image_path.relative_to(target_dir).as_posix()

        parsed_description = parse_game_element_description(full_element.get("descrizione"))
        records.append(
            {
                "id": int(element["id"]),
                "name": element.get("nome"),
                "format": full_element.get("formato_immagine"),
                "image_path": image_relative_path,
                "image_size": image_size,
                "created_at": element.get("data_creazione"),
                "updated_at": element.get("data_ultima_modifica"),
                "description": parsed_description["plain_description"],
                "semantic_hint": parsed_description["semantic_hint"],
                "memory_note": parsed_description["memory_note"],
                "metadata_blocks": parsed_description["metadata_blocks"],
            }
        )

    return records


def _collect_learning_sessions(recovered_sessions_dir: Path | None = None) -> list[dict[str, Any]]:
    sessions = []
    for macro in sorted(get_all_macros(), key=lambda item: int(item["id"])):
        if macro.get("system_key") not in SHARED_MACRO_SYSTEM_KEYS:
            continue
        events = load_macro_events(macro["id"])
        sessions.append(
            {
                "macro_id": int(macro["id"]),
                "name": macro.get("nome"),
                "description": macro.get("descrizione"),
                "system_key": macro.get("system_key"),
                "system_payload": macro.get("system_payload"),
                "created_at": macro.get("data_creazione"),
                "updated_at": macro.get("data_ultima_modifica"),
                "click_sequence": [_compact_click_event(event) for event in events if _is_click_down_event(event)],
            }
        )
    recovered_sessions_dir = recovered_sessions_dir or SHARED_KNOWLEDGE_DIR / "recovered_learning_sessions"
    if recovered_sessions_dir.exists():
        from services.learning_session_recovery_service import load_recovered_learning_sessions

        known_names = {item.get("name") for item in sessions}
        for recovered in load_recovered_learning_sessions(recovered_sessions_dir):
            if recovered.get("name") not in known_names:
                sessions.append(recovered)
    return sessions


def _compact_click_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "time": event.get("time"),
        "x": event.get("x"),
        "y": event.get("y"),
        "normalized_x": event.get("normalized_x"),
        "normalized_y": event.get("normalized_y"),
        "game_element_id": event.get("game_element_id"),
        "previous_game_element_id": event.get("previous_game_element_id"),
        "ui_graph_id": event.get("ui_graph_id"),
        "ui_node_id": event.get("ui_node_id"),
    }


def _is_click_down_event(event: dict[str, Any]) -> bool:
    return event.get("type") == "mouse" and event.get("event") == "down"


def _serialize_default_ui_graph() -> dict[str, Any]:
    graph = build_default_doomsday_ui_graph()
    serialized = asdict(graph)
    serialized["schema"] = "doomsday.ui_semantic_graph.v1"
    return serialized


def _collect_pattern_suggestions() -> list[dict[str, Any]]:
    return [
        asdict(pattern)
        for pattern in suggest_repeated_learning_patterns(min_count=2, max_pattern_length=4)
    ]


def _strip_embedded_metadata(description: str) -> str:
    stripped = description
    for marker in METADATA_MARKERS:
        marker_index = stripped.find(marker)
        if marker_index >= 0:
            stripped = stripped[:marker_index].rstrip()
    return stripped


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


__all__ = [
    "SHARED_KNOWLEDGE_DIR",
    "export_shared_knowledge",
    "parse_game_element_description",
    "slugify",
]
