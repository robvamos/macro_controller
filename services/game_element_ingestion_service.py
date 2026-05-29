"""Preparazione guidata degli elementi grafici del gioco senza distorsioni."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PreparedGameElementAsset:
    image: object
    storage_format: str
    original_format: str
    original_size: tuple[int, int]
    stored_size: tuple[int, int]
    semantic_hint: str
    notes: tuple[str, ...]


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
