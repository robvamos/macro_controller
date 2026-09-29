"""Export shared Doomsday learning knowledge into versionable files."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
import unicodedata
from dataclasses import asdict
from pathlib import Path
from typing import Any

from doomsday.vision.ui_graph import build_default_doomsday_ui_graph
from game_elements import blob_to_image
from core.paths import DOOMSDAY_KNOWLEDGE_DIR, DOOMSDAY_LOCAL_DIR, RECOVERED_LEARNING_SESSIONS_DIR
from repositories.game_element_repository import get_all_game_elements, get_game_element_by_id
from repositories.macro_repository import get_all_macros, load_macro_events
from services.learning_pattern_service import LEARNING_SYSTEM_KEYS


SHARED_KNOWLEDGE_DIR = DOOMSDAY_KNOWLEDGE_DIR
GAME_ELEMENT_IMAGE_DIR_NAME = "game_elements"
LOCAL_ONLY_FIELDS = {
    "computer_name",
    "device_name",
    "host_name",
    "launcher_shortcut",
    "local_workstation",
    "macro_id",
    "macro_name",
    "machine_id",
    "source_database",
    "source_macro_id",
    "source_macro_ids",
    "source_macro_name",
    "user",
    "user_id",
    "user_name",
    "username",
    "workstation",
    "workstation_id",
}
LOCAL_ONLY_PATH_FIELDS = {
    "android_vm_config",
    "android_vm_disk",
    "configuration_path",
    "frame_path",
    "full_frame_path",
    "game_install_dir",
    "install_directory",
    "install_root",
    "launcher_shortcut",
    "launcher_target",
    "network_observer_dir",
    "python_exe",
    "runtime_dir",
    "shortcut_path",
    "source_path",
    "tesseract_exe",
    "virtualbox_install_dir",
    "virtualbox_directory",
}
LOCAL_DISPLAY_FIELDS = {
    "capture_bounds",
    "crop_bounds",
    "click_position",
    "display_bounds",
    "monitor_id",
    "screen_position",
    "screen_resolution",
    "window_bounds",
    "window_rect",
}
METADATA_MARKERS = (
    "AUTO_CLICK_ELEMENT_METADATA:",
    "GENERAL_CLICK_SEMANTIC_NOTE:",
    "SYSTEM_GAME_ELEMENT:",
)
SHARED_MACRO_SYSTEM_KEYS = LEARNING_SYSTEM_KEYS


def export_shared_knowledge(output_dir: Path | str = SHARED_KNOWLEDGE_DIR) -> dict[str, Any]:
    """Write the common learning graph, element catalog and pattern hints to disk."""
    target_dir = Path(output_dir)
    image_dir = target_dir / GAME_ELEMENT_IMAGE_DIR_NAME
    image_dir.mkdir(parents=True, exist_ok=True)

    element_path = target_dir / "game_elements_manifest.json"
    sessions_path = target_dir / "learning_sessions.json"
    graph_path = target_dir / "ui_semantic_graph.json"
    patterns_path = target_dir / "pattern_suggestions.json"
    hero_observations_path = target_dir / "hero_learning_observations"

    existing_elements = _read_json(element_path, {"game_elements": []}).get("game_elements", [])
    existing_elements, existing_id_map = _normalize_existing_game_elements(
        existing_elements, target_dir, image_dir
    )
    local_elements = _export_game_elements(target_dir, image_dir)
    element_records, local_to_shared_id = _merge_game_elements(existing_elements, local_elements)
    shared_ids = {_positive_id(record.get("id")) for record in element_records}

    existing_sessions = _read_json(sessions_path, {"learning_sessions": []}).get("learning_sessions", [])
    existing_sessions = [
        _remap_session_element_ids(item, existing_id_map, preserve_unknown=True, known_ids=shared_ids)
        for item in existing_sessions
        if isinstance(item, dict)
    ]
    local_sessions = _collect_learning_sessions(RECOVERED_LEARNING_SESSIONS_DIR)
    local_sessions = [
        _remap_session_element_ids(item, local_to_shared_id, preserve_unknown=False, known_ids=shared_ids)
        for item in local_sessions
    ]
    sessions = _merge_records(existing_sessions, local_sessions, collection_key="learning_sessions")

    existing_graph = _read_json(graph_path, {})
    ui_graph = _merge_ui_graph(existing_graph, _serialize_default_ui_graph())
    # Pattern suggestions are derived from the merged, canonical sessions. The
    # local pattern service uses workstation-local macro IDs and therefore is
    # not a portable source for this file.
    patterns = _build_shared_pattern_suggestions(sessions, element_records)
    hero_observation_count = _merge_hero_observations(
        DOOMSDAY_LOCAL_DIR / "hero_learning_observations",
        hero_observations_path,
        local_to_shared_id,
        existing_id_map=existing_id_map,
        known_ids=shared_ids,
    )

    _write_json(element_path, {"game_elements": element_records})
    _write_json(sessions_path, {"learning_sessions": sessions})
    _write_json(graph_path, ui_graph)
    _write_json(patterns_path, {"pattern_suggestions": patterns})
    _prune_unreferenced_private_images(image_dir, element_records)

    return {
        "output_dir": str(target_dir),
        "game_elements": len(element_records),
        "learning_sessions": len(sessions),
        "ui_nodes": len(ui_graph["nodes"]),
        "ui_edges": len(ui_graph["edges"]),
        "pattern_suggestions": len(patterns),
        "hero_observations": hero_observation_count,
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
    elements = sorted(get_all_game_elements(), key=lambda item: int(item["id"]))
    records: list[dict[str, Any]] = []

    for element in elements:
        full_element = get_game_element_by_id(element["id"]) or element
        image_relative_path = None
        image_size = None
        image_hash = None
        image_blob = full_element.get("immagine")
        if image_blob:
            image = blob_to_image(image_blob, full_element.get("formato_immagine") or "PNG")
            image_size = {"width": image.width, "height": image.height}
            image_hash = _image_pixel_hash(image)
            name = _portable_element_name(str(element.get("nome") or ""), image_hash)
            image_name = _image_filename(name, image_hash)
            image_path = image_dir / image_name
            image.save(image_path, format="PNG")
            image_relative_path = image_path.relative_to(target_dir).as_posix()
        else:
            name = _portable_element_name(str(element.get("nome") or ""), None)
            if not name:
                continue

        parsed_description = parse_game_element_description(full_element.get("descrizione"))
        records.append(
            {
                "id": int(element["id"]),
                "name": name,
                "format": full_element.get("formato_immagine"),
                "image_path": image_relative_path,
                "image_paths": [image_relative_path] if image_relative_path else [],
                "image_hash": image_hash,
                "image_hashes": [image_hash] if image_hash else [],
                "image_size": image_size,
                "created_at": element.get("data_creazione"),
                "updated_at": element.get("data_ultima_modifica"),
                "description": _sanitize_shared_text(parsed_description["plain_description"]),
                "semantic_hint": parsed_description["semantic_hint"],
                "memory_note": parsed_description["memory_note"],
                "metadata_blocks": parsed_description["metadata_blocks"],
            }
        )

    return [_sanitize_portable(record) for record in records]


def _image_pixel_hash(image: Any) -> str:
    normalized = image.convert("RGBA")
    digest = hashlib.sha256()
    digest.update(f"{normalized.width}x{normalized.height}:RGBA\0".encode("ascii"))
    digest.update(normalized.tobytes())
    return digest.hexdigest()


def _image_filename(name: str, image_hash: str) -> str:
    normalized_click_name = f"observed_click_{image_hash[:16]}"
    if name.casefold() == normalized_click_name:
        return f"{normalized_click_name}.png"
    return f"{slugify(name)}_{image_hash[:16]}.png"


def _portable_element_name(name: str, image_hash: str | None) -> str:
    if re.search(r"(?i)recorded[_ -]?click|\blocale\b|local[_ -]?workstation", name):
        if image_hash:
            return f"observed_click_{image_hash[:16]}"
        return ""
    return name.strip()


def _normalize_existing_game_elements(
    records: list[Any], target_dir: Path, image_dir: Path
) -> tuple[list[dict[str, Any]], dict[int, int]]:
    """Migrate older shared records to content-addressed, workstation-neutral assets."""
    normalized: list[dict[str, Any]] = []
    old_to_new: dict[int, int] = {}
    for source in sorted(
        (item for item in records if isinstance(item, dict)),
        key=lambda item: _positive_id(item.get("id")),
    ):
        record = _sanitize_portable(source)
        old_id = _positive_id(source.get("id"))
        relative_images = source.get("image_paths") or [source.get("image_path")]
        image_paths: list[str] = []
        image_hashes: list[str] = []
        first_size = source.get("image_size")
        for relative in relative_images:
            if not isinstance(relative, str) or not relative:
                continue
            candidate = (target_dir / relative).resolve()
            if target_dir.resolve() not in candidate.parents or not candidate.is_file():
                continue
            try:
                from PIL import Image

                with Image.open(candidate) as opened:
                    image = opened.convert("RGBA")
            except (OSError, ValueError):
                continue
            image_hash = _image_pixel_hash(image)
            name = _portable_element_name(str(source.get("name") or ""), image_hash)
            if not name:
                continue
            destination = image_dir / _image_filename(name, image_hash)
            if not destination.is_file():
                image.save(destination, format="PNG")
            image_paths.append(destination.relative_to(target_dir).as_posix())
            image_hashes.append(image_hash)
            if first_size is None:
                first_size = {"width": image.width, "height": image.height}

        name = _portable_element_name(str(source.get("name") or ""), image_hashes[0] if image_hashes else None)
        if not name:
            # An image-less workstation observation cannot be identified safely.
            continue
        record.update(
            {
                "name": name,
                "image_path": image_paths[0] if image_paths else None,
                "image_paths": _merge_string_values([], image_paths),
                "image_hash": image_hashes[0] if image_hashes else None,
                "image_hashes": image_hashes,
                "image_size": first_size,
            }
        )
        before_ids = {old_id} if old_id else set()
        normalized, mapping = _merge_game_elements(normalized, [record])
        if old_id:
            old_to_new[old_id] = mapping.get(_positive_id(record.get("id")), _positive_id(record.get("id")))
            # _merge_game_elements maps the record's preferred/source ID to its
            # final ID; retain a direct map even when a damaged ID was omitted.
            if not old_to_new[old_id] and before_ids:
                old_to_new[old_id] = _positive_id(normalized[-1].get("id"))
    return normalized, old_to_new


def _prune_unreferenced_private_images(image_dir: Path, records: list[dict[str, Any]]) -> None:
    referenced = set()
    for record in records:
        for relative in record.get("image_paths") or [record.get("image_path")]:
            if isinstance(relative, str) and relative:
                referenced.add(Path(relative).name.casefold())
    private_name = re.compile(
        r"(?i)(?:recorded[_ -]?click|locale|antartika|musicstati|robva|roberto|"
        r"observed_click_[0-9a-f]{16}_[0-9a-f]{16})"
    )
    for path in image_dir.glob("*.png"):
        if path.name.casefold() not in referenced and private_name.search(path.name):
            path.unlink()


def _collect_learning_sessions(recovered_sessions_dir: Path | None = None) -> list[dict[str, Any]]:
    sessions = []
    for macro in sorted(get_all_macros(), key=lambda item: int(item["id"])):
        if macro.get("system_key") not in SHARED_MACRO_SYSTEM_KEYS:
            continue
        events = load_macro_events(macro["id"])
        system_key = macro.get("system_key")
        sessions.append(
            _portable_learning_session(
                {
                    "name": system_key or macro.get("nome"),
                    "description": macro.get("descrizione"),
                    "system_key": system_key,
                    "system_payload": macro.get("system_payload") or {},
                    "created_at": macro.get("data_creazione"),
                    "updated_at": macro.get("data_ultima_modifica"),
                    "click_sequence": [
                        _compact_click_event(event)
                        for event in events
                        if _is_click_down_event(event)
                    ],
                }
            )
        )
    recovered_sessions_dir = recovered_sessions_dir or RECOVERED_LEARNING_SESSIONS_DIR
    if recovered_sessions_dir.exists():
        from services.learning_session_recovery_service import load_recovered_learning_sessions

        for recovered in load_recovered_learning_sessions(recovered_sessions_dir):
            sessions.append(_portable_learning_session(recovered))
    return sessions


def _compact_click_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "time": event.get("time"),
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


def _portable_learning_session(session: dict[str, Any]) -> dict[str, Any]:
    result = _sanitize_portable(session)
    result.pop("macro_id", None)
    result.pop("source_macro_id", None)
    result.pop("source_macro_ids", None)
    system_key = result.get("system_key")
    system_payload = result.get("system_payload")
    if not system_key and isinstance(system_payload, dict):
        system_key = system_payload.get("system_key")
    result["name"] = system_key or "UI learning"
    if not result.get("created_at"):
        result["created_at"] = result.get("updated_at") or result.get("recovered_at")
    if system_key == "launch_game":
        return {}
    click_sequence = result.get("click_sequence")
    if isinstance(click_sequence, list):
        result["click_sequence"] = [
            _sanitize_portable(click) for click in click_sequence if isinstance(click, dict)
        ]
    return result


def _build_shared_pattern_suggestions(
    sessions: list[dict[str, Any]], elements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    from collections import Counter

    element_names = {
        _positive_id(element.get("id")): str(element.get("name") or "")
        for element in elements
        if _positive_id(element.get("id")) and element.get("name")
    }
    counts: Counter[tuple[int, ...]] = Counter()
    session_sources: dict[tuple[int, ...], set[str]] = {}
    total = 0
    for session in sessions:
        session_identity = _record_identity(
            session, collection_key="learning_sessions", identity_fields=None
        )
        sequence = []
        for click in session.get("click_sequence", []):
            element_id = _positive_id(click.get("game_element_id"))
            if element_id in element_names:
                sequence.append(element_id)
        for length in range(2, min(4, len(sequence)) + 1):
            for start in range(len(sequence) - length + 1):
                pattern = tuple(sequence[start : start + length])
                counts[pattern] += 1
                session_sources.setdefault(pattern, set()).add(session_identity)
                total += 1

    suggestions = []
    for pattern, count in counts.items():
        source_count = len(session_sources[pattern])
        if source_count < 2:
            continue
        names = [element_names[element_id] for element_id in pattern]
        suggestions.append(
            {
                "element_ids": list(pattern),
                "element_names": names,
                "count": count,
                "source_session_count": source_count,
                "confidence": round(count / (total or 1), 4),
                "suggested_macro_name": "Macro candidata: " + " → ".join(names),
                "notes": (
                    "Candidato derivato da sequenze osservate in sessioni distinte; "
                    "richiede revisione e conferma umana."
                ),
            }
        )
    suggestions.sort(
        key=lambda item: (item["source_session_count"], item["count"], len(item["element_ids"])),
        reverse=True,
    )
    return suggestions


def _merge_hero_observations(
    source_dir: Path,
    shared_dir: Path,
    id_map: dict[int, int] | None = None,
    *,
    existing_id_map: dict[int, int] | None = None,
    known_ids: set[int] | None = None,
) -> int:
    """Publish OCR evidence without machine-specific names or frame paths."""
    if not source_dir.is_dir() and not shared_dir.is_dir():
        return 0
    shared_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(source_dir.glob("*.json")) if source_dir.is_dir() else []:
        payload = _read_json(source, {})
        if not isinstance(payload, dict):
            continue
        portable = _sanitize_portable(payload)
        portable = _remap_observation_element_ids(
            portable, id_map or {}, preserve_unknown=False, known_ids=known_ids
        )
        portable["session_name"] = f"hero-inspection {source.stem}"
        _write_additive_observation(shared_dir, source.stem, portable)

    # Clean older published records as well, so workstation paths do not remain
    # in the canonical folder after upgrading from the previous layout.
    for destination in sorted(shared_dir.glob("*.json")):
        payload = _read_json(destination, {})
        if not isinstance(payload, dict):
            continue
        portable = _sanitize_portable(payload)
        portable = _remap_observation_element_ids(
            portable,
            existing_id_map or {},
            preserve_unknown=True,
            known_ids=known_ids,
        )
        portable["session_name"] = f"hero-inspection {destination.stem}"
        _write_json(destination, portable)
    return len(list(shared_dir.glob("*.json")))


def _write_additive_observation(shared_dir: Path, stem: str, payload: dict[str, Any]) -> None:
    destination = shared_dir / f"{stem}.json"
    if destination.exists():
        existing = _read_json(destination, {})
        if _stable_json(existing) == _stable_json(payload):
            return
        encoded = _stable_json(payload)
        suffix = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:8]
        destination = shared_dir / f"{stem}_{suffix}.json"
        if destination.exists():
            existing = _read_json(destination, {})
            if _stable_json(existing) == _stable_json(payload):
                return
            raise FileExistsError(f"Conflicting shared hero observation: {destination.name}")
    _write_json(destination, payload)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _strip_embedded_metadata(description: str) -> str:
    stripped = description
    for marker in METADATA_MARKERS:
        marker_index = stripped.find(marker)
        if marker_index >= 0:
            stripped = stripped[:marker_index].rstrip()
    return stripped


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _merge_game_elements(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, int]]:
    """Keep shared element IDs stable while adding elements from a local DB."""
    merged = [_sanitize_portable(record) for record in existing if isinstance(record, dict)]
    index_by_name = {
        _element_name_key(str(record.get("name") or "")): index
        for index, record in enumerate(merged)
        if record.get("name")
    }
    next_id = max((int(record.get("id") or 0) for record in merged), default=0) + 1
    local_to_shared_id: dict[int, int] = {}

    for local_record in incoming:
        name = str(local_record.get("name") or "")
        if not name:
            continue
        key = _element_name_key(name)
        index = index_by_name.get(key)
        if index is None:
            try:
                preferred_id = int(local_record.get("id") or 0)
            except (TypeError, ValueError):
                preferred_id = 0
            used_ids = {_positive_id(record.get("id")) for record in merged}
            if preferred_id > 0 and preferred_id not in used_ids:
                shared_id = preferred_id
            else:
                while next_id in used_ids:
                    next_id += 1
                shared_id = next_id
                next_id += 1
            record = {**deepcopy(local_record), "id": shared_id}
            if record.get("image_path"):
                record["image_paths"] = [record["image_path"]]
            merged.append(record)
            index_by_name[key] = len(merged) - 1
        else:
            existing_record = merged[index]
            shared_id = _positive_id(existing_record.get("id")) or next_id
            record = {**deepcopy(existing_record), "id": shared_id}
            old_paths = existing_record.get("image_paths") or [existing_record.get("image_path")]
            new_paths = local_record.get("image_paths") or [local_record.get("image_path")]
            old_hashes = existing_record.get("image_hashes") or [existing_record.get("image_hash")]
            new_hashes = local_record.get("image_hashes") or [local_record.get("image_hash")]
            hash_by_path = {
                path: image_hash
                for path, image_hash in [*zip(old_paths, old_hashes), *zip(new_paths, new_hashes)]
                if path and image_hash
            }
            record["image_paths"] = _merge_string_values(old_paths, new_paths)
            record["image_hashes"] = [hash_by_path.get(path) for path in record["image_paths"]]
            if not record.get("image_path") and record["image_paths"]:
                record["image_path"] = record["image_paths"][0]
            if record.get("image_path"):
                record["image_hash"] = hash_by_path.get(record["image_path"])
            for field, value in local_record.items():
                if field in {"id", "metadata_blocks", "image_path", "image_paths", "image_hash", "image_hashes"} or value is None or value == "" or value == [] or value == {}:
                    continue
                if field == "image_size":
                    record.setdefault("image_size", value)
                elif field == "description":
                    record["description"] = _merge_text(record.get(field), value)
                elif field in {"semantic_hint", "memory_note"}:
                    record[field] = _merge_text(record.get(field), value)
                elif field in {"created_at", "updated_at"}:
                    record[field] = max(str(record.get(field) or ""), str(value or "")) or None
                else:
                    record[field] = deepcopy(value)
            record["metadata_blocks"] = _merge_metadata_blocks(
                existing_record.get("metadata_blocks", {}), local_record.get("metadata_blocks", {})
            )
            merged[index] = record
        try:
            local_to_shared_id[int(local_record["id"])] = shared_id
        except (KeyError, TypeError, ValueError):
            continue
    return merged, local_to_shared_id


def _element_name_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _positive_id(value: Any) -> int:
    try:
        result = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return result if result > 0 else 0


def _merge_string_values(existing: Any, incoming: Any) -> list[str]:
    values = []
    for collection in (existing, incoming):
        if isinstance(collection, str):
            collection = [collection]
        if not isinstance(collection, (list, tuple)):
            continue
        for value in collection:
            if isinstance(value, str) and value and value not in values:
                values.append(value)
    return values


def _merge_text(existing: Any, incoming: Any) -> str:
    values = _merge_string_values(existing, incoming)
    return "\n\n".join(values)


def _remap_session_element_ids(
    session: dict[str, Any],
    id_map: dict[int, int],
    *,
    preserve_unknown: bool = False,
    known_ids: set[int] | None = None,
) -> dict[str, Any]:
    result = deepcopy(_portable_learning_session(session))
    return _remap_observation_element_ids(
        result, id_map, preserve_unknown=preserve_unknown, known_ids=known_ids
    )


def _remap_observation_element_ids(
    value: Any,
    id_map: dict[int, int],
    *,
    preserve_unknown: bool,
    known_ids: set[int] | None = None,
    parent_key: str = "",
) -> Any:
    """Remap IDs recursively in OCR evidence, dropping IDs unknown to this DB."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized_key = str(key).casefold()
            if normalized_key in {"game_element_id", "previous_game_element_id"}:
                try:
                    source_id = int(item) if item is not None else 0
                except (TypeError, ValueError):
                    source_id = 0
                mapped_id = id_map.get(source_id)
                if mapped_id is None and preserve_unknown and source_id > 0:
                    if known_ids is None or source_id in known_ids:
                        mapped_id = source_id
                result[key] = mapped_id
            else:
                result[key] = _remap_observation_element_ids(
                    item,
                    id_map,
                    preserve_unknown=preserve_unknown,
                    known_ids=known_ids,
                    parent_key=normalized_key,
                )
        return result
    if isinstance(value, list):
        if parent_key in {"recorded_click_element_ids", "game_element_ids"}:
            remapped = []
            for item in value:
                try:
                    source_id = int(item)
                except (TypeError, ValueError):
                    continue
                mapped_id = id_map.get(source_id)
                if mapped_id is None and preserve_unknown and source_id > 0:
                    if known_ids is None or source_id in known_ids:
                        mapped_id = source_id
                if mapped_id is not None:
                    remapped.append(mapped_id)
            return remapped
        return [
            _remap_observation_element_ids(
                item,
                id_map,
                preserve_unknown=preserve_unknown,
                known_ids=known_ids,
                parent_key=parent_key,
            )
            for item in value
        ]
    return value


def _merge_records(
    existing: list[Any],
    incoming: list[Any],
    *,
    collection_key: str | None = None,
    identity_fields: tuple[str, ...] | None = None,
) -> list[Any]:
    """Merge records additively so one workstation cannot erase another's facts."""
    merged: list[Any] = []
    index_by_identity: dict[str, int] = {}
    for record in [*existing, *incoming]:
        if not isinstance(record, (dict, list)):
            continue
        record = _sanitize_portable(record)
        if collection_key == "learning_sessions" and isinstance(record, dict):
            record = _portable_learning_session(record)
            if not record or record.get("system_key") == "launch_game":
                continue
        identity = _record_identity(record, collection_key=collection_key, identity_fields=identity_fields)
        if identity in index_by_identity:
            index = index_by_identity[identity]
            if isinstance(record, dict) and isinstance(merged[index], dict):
                merged[index] = _merge_dict_additive(merged[index], record)
            continue
        index_by_identity[identity] = len(merged)
        merged.append(deepcopy(record))
    return merged


def _record_identity(
    record: dict[str, Any] | list[Any],
    *,
    collection_key: str | None,
    identity_fields: tuple[str, ...] | None,
) -> str:
    if identity_fields and isinstance(record, dict):
        payload: Any = {key: record.get(key) for key in identity_fields}
    elif collection_key == "learning_sessions" and isinstance(record, dict):
        payload_data = record.get("system_payload")
        payload = {
            "system_key": record.get("system_key") or (
                payload_data.get("system_key") if isinstance(payload_data, dict) else None
            ),
            "name": record.get("name"),
            "created_at": record.get("created_at"),
            "click_sequence": record.get("click_sequence", []),
        }
    else:
        payload = record
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _merge_dict_additive(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(existing)
    for key, value in incoming.items():
        if key not in result:
            result[key] = deepcopy(value)
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dict_additive(result[key], value)
        elif isinstance(result[key], list) and isinstance(value, list):
            combined = []
            seen = set()
            for item in [*result[key], *value]:
                identity = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                if identity not in seen:
                    seen.add(identity)
                    combined.append(deepcopy(item))
            result[key] = combined
        elif value not in (None, "", [], {}):
            result[key] = deepcopy(value)
    return result


def _merge_ui_graph(existing: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    existing = _sanitize_portable(existing)
    result = {**deepcopy(defaults), **deepcopy(existing)}
    for collection, identity_fields in (
        ("nodes", ("node_id",)),
        ("edges", ("from_node_id", "to_node_id", "trigger")),
    ):
        default_items = defaults.get(collection, [])
        existing_items = existing.get(collection, [])
        result[collection] = _merge_records(
            default_items,
            existing_items,
            identity_fields=identity_fields,
        )
    return result


def _merge_metadata_blocks(existing: Any, incoming: Any) -> dict[str, list[Any]]:
    if not isinstance(existing, dict):
        existing = {}
    if not isinstance(incoming, dict):
        incoming = {}
    merged: dict[str, list[Any]] = {}
    for key in sorted(set(existing) | set(incoming)):
        items = []
        seen = set()
        existing_items = existing.get(key, [])
        incoming_items = incoming.get(key, [])
        if not isinstance(existing_items, list):
            existing_items = [existing_items]
        if not isinstance(incoming_items, list):
            incoming_items = [incoming_items]
        for item in [*existing_items, *incoming_items]:
            identity = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if identity in seen:
                continue
            seen.add(identity)
            items.append(deepcopy(item))
        merged[key] = items
    return merged


def _sanitize_portable(value: Any, *, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            normalized = str(key).casefold()
            if parent_key == "click_sequence" and normalized in {"x", "y"}:
                continue
            if (
                normalized in LOCAL_ONLY_FIELDS
                or normalized in LOCAL_ONLY_PATH_FIELDS
                or normalized in LOCAL_DISPLAY_FIELDS
            ):
                continue
            if normalized.endswith("_path") and isinstance(item, str) and _is_absolute_path(item):
                continue
            cleaned[key] = _sanitize_portable(item, parent_key=normalized)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_portable(item, parent_key=parent_key) for item in value]
    if isinstance(value, str):
        if _is_absolute_path(value):
            return None
        return _sanitize_shared_text(value)
    return value


def _sanitize_shared_text(value: str) -> str:
    lines = []
    for line in value.splitlines():
        if re.search(r"\bMacro sorgente\s*:", line, flags=re.IGNORECASE):
            continue
        if re.search(r"\bLocale\s+[^\r\n]*\\[^\r\n]*", line, flags=re.IGNORECASE):
            continue
        # Remove embedded Windows paths, including paths inside prose or JSON
        # metadata values, while preserving the surrounding semantic sentence.
        line = re.sub(r"(?i)\b[a-z]:[\\/][^\s,;\]\)\}\"]+", "[percorso locale]", line)
        line = re.sub(r"\\\\[^\\\s]+\\[^\s,;\]\)\}\"]+", "[percorso locale]", line)
        if line.strip():
            lines.append(line)
    return "\n".join(lines)


def _is_absolute_path(value: str) -> bool:
    return bool(re.match(r"^(?:[a-z]:[\\/]|\\\\|/)", value, flags=re.IGNORECASE))


__all__ = [
    "SHARED_KNOWLEDGE_DIR",
    "export_shared_knowledge",
    "parse_game_element_description",
    "slugify",
]
