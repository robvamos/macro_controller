"""Import published Doomsday visual knowledge into a workstation's local DB."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from core.paths import DOOMSDAY_KNOWLEDGE_DIR
from repositories.game_element_repository import (
    create_game_element,
    get_all_game_elements,
    update_game_element,
)


SHARED_ELEMENT_MARKER = "SHARED_KNOWLEDGE_ID:"
SHARED_IMAGE_MARKER = "SHARED_KNOWLEDGE_IMAGE:"
_METADATA_MARKERS = {
    "auto_click_element_metadata": "AUTO_CLICK_ELEMENT_METADATA:",
    "general_click_semantic_note": "GENERAL_CLICK_SEMANTIC_NOTE:",
    "system_game_element": "SYSTEM_GAME_ELEMENT:",
}


def import_shared_game_elements(
    knowledge_dir: str | Path = DOOMSDAY_KNOWLEDGE_DIR,
) -> dict[str, int]:
    """Add shared templates locally while preserving workstation-owned variants."""
    root = Path(knowledge_dir).resolve()
    manifest_path = root / "game_elements_manifest.json"
    if not manifest_path.is_file():
        return {"imported": 0, "updated": 0, "skipped": 0, "missing_images": 0}

    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    records = payload.get("game_elements", [])
    existing = {str(item.get("nome") or "").casefold(): item for item in get_all_game_elements(include_image=True)}
    result = {"imported": 0, "updated": 0, "skipped": 0, "missing_images": 0}

    for record in records:
        base_name = str(record.get("name") or "").strip()
        relative_images = record.get("image_paths") or [record.get("image_path")]
        relative_images = [value for value in relative_images if isinstance(value, str) and value]
        if not base_name or not relative_images:
            result["skipped"] += 1
            continue
        next_variant = 1
        image_hashes = record.get("image_hashes")
        if not isinstance(image_hashes, list):
            image_hashes = []
        expected_hash = record.get("image_hash")
        seen_images: set[str] = set()
        for image_index, relative_image in enumerate(relative_images):
            if relative_image in seen_images:
                continue
            seen_images.add(relative_image)
            image_path = (root / relative_image).resolve()
            if root not in image_path.parents or not image_path.is_file():
                result["missing_images"] += 1
                continue
            image_blob = image_path.read_bytes()
            declared_hash = image_hashes[image_index] if image_index < len(image_hashes) else None
            if image_index == 0 and not declared_hash:
                declared_hash = expected_hash
            image_hash = (
                str(declared_hash)[:64]
                if isinstance(declared_hash, str) and declared_hash
                else hashlib.sha256(image_blob).hexdigest()[:16]
            )
            description = _build_description(record, image_hash=image_hash)
            existing_shared = next(
                (
                    item
                    for item in existing.values()
                    if f"{SHARED_ELEMENT_MARKER} {record.get('id', '')}" in str(item.get("descrizione") or "")
                    and f"{SHARED_IMAGE_MARKER} {image_hash}" in str(item.get("descrizione") or "")
                ),
                None,
            )
            if existing_shared:
                old_description = str(existing_shared.get("descrizione") or "")
                merged_description = _merge_description(old_description, description)
                if merged_description != old_description:
                    update_game_element(int(existing_shared["id"]), descrizione=merged_description)
                    existing_shared["descrizione"] = merged_description
                    result["updated"] += 1
                else:
                    result["skipped"] += 1
                continue
            while True:
                name = base_name if next_variant == 1 else f"{base_name}_{next_variant}"
                next_variant += 1
                local = existing.get(name.casefold())
                if local and SHARED_ELEMENT_MARKER not in str(local.get("descrizione") or ""):
                    continue
                break
            if local:
                # A marked entry for another visual version is kept as a variant.
                # Local edits remain intact; the new shared image gets its own row.
                continue

            try:
                element_id = create_game_element(name, description, image_blob, "PNG")
            except ValueError:
                # A concurrent local capture may have added the same name after the
                # initial lookup. Keep the user's record intact.
                result["skipped"] += 1
                continue
            existing[name.casefold()] = {
                "id": element_id,
                "nome": name,
                "descrizione": description,
                "immagine": image_blob,
                "formato_immagine": "PNG",
            }
            result["imported"] += 1
    return result


def _build_description(record: dict[str, Any], *, image_hash: str) -> str:
    parts = [str(record.get("description") or "").strip()]
    semantic_hint = str(record.get("semantic_hint") or "").strip()
    if semantic_hint:
        parts.append(f"[semantic_hint] {semantic_hint}")
    memory_note = str(record.get("memory_note") or "").strip()
    if memory_note:
        parts.append(f"MEMORIA SEMANTICA: {memory_note}")

    blocks = record.get("metadata_blocks")
    if isinstance(blocks, dict):
        for key, values in blocks.items():
            marker = _METADATA_MARKERS.get(str(key).casefold())
            if not marker:
                continue
            if not isinstance(values, list):
                values = [values]
            for value in values:
                parts.append(f"{marker}{json.dumps(value, ensure_ascii=False, sort_keys=True)}")
    parts.append(f"{SHARED_ELEMENT_MARKER} {record.get('id', '')}")
    parts.append(f"{SHARED_IMAGE_MARKER} {image_hash}")
    return "\n".join(part for part in parts if part)


def _merge_description(existing: str, incoming: str) -> str:
    lines = [line for line in existing.splitlines() if line.strip()]
    seen = set(lines)
    for line in incoming.splitlines():
        if line.strip() and line not in seen:
            lines.append(line)
            seen.add(line)
    return "\n".join(lines)


__all__ = ["SHARED_ELEMENT_MARKER", "SHARED_IMAGE_MARKER", "import_shared_game_elements"]
