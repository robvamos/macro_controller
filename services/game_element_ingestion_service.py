"""Preparazione guidata e deduplica degli elementi grafici del gioco."""

from __future__ import annotations

from dataclasses import dataclass
import re

from doomsday.vision.click_context_guard import close_image, compute_context_similarity
from game_elements import blob_to_image, image_to_blob
from repositories.game_element_repository import (
    create_game_element,
    get_all_game_elements,
    update_game_element,
)


STRUCTURED_METADATA_MARKERS = (
    "AUTO_CLICK_ELEMENT_METADATA:",
    "GENERAL_CLICK_SEMANTIC_NOTE:",
)
DEFAULT_DUPLICATE_ELEMENT_SIMILARITY = 0.93


@dataclass(slots=True)
class PreparedGameElementAsset:
    image: object
    storage_format: str
    original_format: str
    original_size: tuple[int, int]
    stored_size: tuple[int, int]
    semantic_hint: str
    notes: tuple[str, ...]


@dataclass(slots=True)
class GameElementUpsertResult:
    element_id: int
    element_name: str
    reused_existing: bool
    updated_existing: bool


def build_game_element_ingestion_guidelines() -> tuple[str, ...]:
    return (
        "1. Cattura solo il simbolo o pannello davvero utile, senza UI extra non necessaria.",
        "2. Mantieni l'immagine nel suo rapporto originale: il salvataggio non la stira né la ridimensiona.",
        "3. Se l'elemento contiene testo che puo' cambiare lingua, privilegia il simbolo stabile e non la scritta.",
        "4. Se un elemento esiste gia', riusalo e aggiungi nuove caratteristiche invece di duplicarlo.",
        "5. Dai un nome descrittivo e spiega cosa rappresenta o dove compare nel gioco.",
        "6. Se l'elemento serve per recovery o navigazione, annota anche come va usato.",
        "7. Se ci sono badge rossi, numeri o puntini variabili, trattali come rumore e non come parte del riferimento stabile.",
        "8. Preferisci immagini nitide e ritagli stretti, cosi' il matching resta piu' affidabile.",
    )


def prepare_game_element_asset(image, *, source_format=None, semantic_hint="") -> PreparedGameElementAsset:
    """Normalizza l'asset per lo storage senza alterarne le proporzioni."""
    if image is None:
        raise ValueError("Nessuna immagine da preparare.")

    original_format = (source_format or getattr(image, "format", None) or "PNG").upper()
    original_size = tuple(getattr(image, "size", (0, 0)))
    if original_size == (0, 0):
        raise ValueError("Immagine non valida.")

    normalized = image.copy()
    if normalized.mode not in ("RGB", "RGBA"):
        if "A" in normalized.getbands():
            normalized = normalized.convert("RGBA")
        else:
            normalized = normalized.convert("RGB")

    storage_format = "PNG"
    notes = (
        "storage_lossless_png",
        "aspect_ratio_preserved",
        "no_resize_applied",
    )
    return PreparedGameElementAsset(
        image=normalized,
        storage_format=storage_format,
        original_format=original_format,
        original_size=original_size,
        stored_size=tuple(normalized.size),
        semantic_hint=(semantic_hint or "").strip(),
        notes=notes,
    )


def build_prepared_asset_summary(asset: PreparedGameElementAsset) -> str:
    width, height = asset.stored_size
    orig_width, orig_height = asset.original_size
    semantic_line = f"\nRuolo semantico: {asset.semantic_hint}" if asset.semantic_hint else ""
    return (
        f"Origine: {asset.original_format} {orig_width}x{orig_height}\n"
        f"Salvataggio: {asset.storage_format} {width}x{height} (senza distorsioni){semantic_line}"
    )


def build_game_element_description(description_text, semantic_hint):
    description = (description_text or "").strip()
    semantic_hint = (semantic_hint or "").strip()
    if semantic_hint:
        return f"{description}\n[semantic_hint] {semantic_hint}".strip()
    return description


def create_or_merge_game_element(
    nome,
    descrizione,
    image,
    formato_immagine,
    *,
    ignore_element_id=None,
    similarity_threshold=DEFAULT_DUPLICATE_ELEMENT_SIMILARITY,
):
    """Crea un nuovo elemento oppure riusa/arricchisce quello gia' presente."""
    matched_element = find_matching_game_element(
        image,
        similarity_threshold=similarity_threshold,
        ignore_element_id=ignore_element_id,
    )
    if matched_element is not None:
        merged_description = merge_game_element_descriptions(
            matched_element.get("descrizione"),
            descrizione,
        )
        updated_existing = merged_description != (matched_element.get("descrizione") or "")
        if updated_existing:
            update_game_element(int(matched_element["id"]), descrizione=merged_description)
        return GameElementUpsertResult(
            element_id=int(matched_element["id"]),
            element_name=matched_element["nome"],
            reused_existing=True,
            updated_existing=updated_existing,
        )

    image_blob = image_to_blob(image, formato_immagine)
    element_id = _create_unique_game_element(nome, descrizione, image_blob, formato_immagine)
    return GameElementUpsertResult(
        element_id=element_id,
        element_name=nome,
        reused_existing=False,
        updated_existing=False,
    )


def find_matching_game_element(image, *, similarity_threshold=DEFAULT_DUPLICATE_ELEMENT_SIMILARITY, ignore_element_id=None):
    for element in get_all_game_elements(include_image=True):
        if ignore_element_id is not None and int(element["id"]) == int(ignore_element_id):
            continue
        existing_blob = element.get("immagine")
        if not existing_blob:
            continue
        existing_image = None
        try:
            existing_image = blob_to_image(existing_blob, element.get("formato_immagine") or "PNG")
            if not sizes_are_compatible(image.size, existing_image.size):
                continue
            score = compute_context_similarity(
                existing_image,
                image,
                resize_px=48,
                translation_tolerance_px=2,
            )
            if score >= similarity_threshold:
                return element
        except Exception:
            continue
        finally:
            close_image(existing_image)
    return None


def sizes_are_compatible(size_a, size_b, *, tolerance_ratio=0.18):
    width_a, height_a = size_a
    width_b, height_b = size_b
    if min(width_a, height_a, width_b, height_b) <= 0:
        return False
    width_delta = abs(width_a - width_b) / float(max(width_a, width_b))
    height_delta = abs(height_a - height_b) / float(max(height_a, height_b))
    return width_delta <= tolerance_ratio and height_delta <= tolerance_ratio


def merge_game_element_descriptions(existing_description, new_description):
    existing = (existing_description or "").strip()
    incoming = (new_description or "").strip()
    if not incoming:
        return existing
    if not existing:
        return incoming
    if incoming in existing:
        return existing

    semantic_hint = extract_semantic_hint(incoming)
    merged = existing
    if semantic_hint and semantic_hint not in existing:
        merged = f"{merged}\n[semantic_hint] {semantic_hint}".strip()

    for marker in STRUCTURED_METADATA_MARKERS:
        block = extract_marker_block(incoming, marker)
        if block and block not in merged:
            merged = f"{merged}\n{block}".strip()

    plain_incoming = strip_structured_metadata(incoming)
    if plain_incoming and plain_incoming not in merged:
        merged = f"{merged}\n{plain_incoming}".strip()
    return merged


def extract_semantic_hint(description):
    match = re.search(r"\[semantic_hint\]\s*(.+)", description or "")
    return match.group(1).strip() if match else ""


def extract_marker_block(description, marker):
    if not description:
        return ""
    marker_index = description.find(marker)
    if marker_index < 0:
        return ""
    return description[marker_index:].strip()


def strip_structured_metadata(description):
    cleaned = description or ""
    semantic_marker = "[semantic_hint]"
    if semantic_marker in cleaned:
        cleaned = cleaned.split(semantic_marker, 1)[0]
    for marker in STRUCTURED_METADATA_MARKERS:
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0]
    return cleaned.strip()


def _create_unique_game_element(base_name, description, image_blob, image_format):
    candidate = base_name
    suffix = 2
    while True:
        try:
            return create_game_element(candidate, description, image_blob, image_format)
        except ValueError as exc:
            if "esiste" not in str(exc):
                raise
            candidate = f"{base_name}_{suffix}"
            suffix += 1


__all__ = [
    "DEFAULT_DUPLICATE_ELEMENT_SIMILARITY",
    "GameElementUpsertResult",
    "PreparedGameElementAsset",
    "build_game_element_description",
    "build_game_element_ingestion_guidelines",
    "build_prepared_asset_summary",
    "create_or_merge_game_element",
    "extract_marker_block",
    "extract_semantic_hint",
    "find_matching_game_element",
    "merge_game_element_descriptions",
    "prepare_game_element_asset",
    "sizes_are_compatible",
    "strip_structured_metadata",
]
