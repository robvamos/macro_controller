"""Conservative full-frame OCR classification for learned hero screens."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True, slots=True)
class HeroScreenClassification:
    node_id: str
    confidence: float
    matched_anchors: tuple[str, ...]
    status: str


RULES = (
    (
        "hero_equipment_item_detail_view",
        ("armamenti dell eroe", "in possesso", "effetti abilita"),
        2,
    ),
    (
        "hero_equipment_view",
        ("armamenti dell eroe", "panoramica degli attributi di armamento", "attributi di base"),
        2,
    ),
    (
        "hero_talents_detail_view",
        ("punti talento", "consigliato", "squadra rider", "ammazzazombi"),
        1,
    ),
    (
        "hero_skills_detail_view",
        ("info abilita eroe", "abilita e al livello", "anteprima miglioramento", "battaglia"),
        2,
    ),
    (
        "hero_profile_view",
        ("livello", "esp", "squadra", "dan", "dif", "ps"),
        4,
    ),
    (
        "home_view",
        ("zaino", "alleanza", "bestia", "eroe", "regione"),
        3,
    ),
)


def classify_hero_screen(ocr_text: str) -> HeroScreenClassification:
    normalized = _normalize(ocr_text)
    best = HeroScreenClassification("unknown_main_view", 0.0, (), "observed_unlabeled")
    for node_id, anchors, minimum in RULES:
        matched = tuple(anchor for anchor in anchors if anchor in normalized)
        if len(matched) < minimum:
            continue
        confidence = min(0.99, 0.55 + 0.44 * len(matched) / len(anchors))
        candidate = HeroScreenClassification(node_id, round(confidence, 3), matched, "labeled")
        if candidate.confidence > best.confidence:
            best = candidate
    return best


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_like = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_like.casefold()).strip()


__all__ = ["HeroScreenClassification", "classify_hero_screen"]
