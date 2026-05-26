"""Pipeline OCR per screenshot eroi/talenti."""

from __future__ import annotations

import json
from pathlib import Path

from doomsday.config import DEFAULT_STAT_VALUES, DOOMSDAY_OCR_OUTPUT_DIR
from doomsday.ocr.stats_parser import parse_stats_from_ocr
from doomsday.ocr.talents_parser import parse_talents_from_ocr


def extract_hero_name(image_path: str | Path) -> str:
    """Deriva il nome eroe dal nome file."""
    return Path(image_path).stem


def analyze_ocr_text(ocr_text: str) -> tuple[dict, int]:
    """Analizza un blocco OCR e prova statistiche, poi talenti."""
    stats_data, defaults_used = parse_stats_from_ocr(ocr_text)
    non_default_stats = any(
        stats_data[key] != DEFAULT_STAT_VALUES[key]
        for key in ("ATK", "DEF", "HP", "SPD")
    )
    if non_default_stats:
        return stats_data, defaults_used

    talents_data = parse_talents_from_ocr(ocr_text)
    return talents_data, defaults_used


def analyze_image(image_path: str | Path, *, image_to_text=None, tesseract_lang: str = "eng") -> tuple[dict, int]:
    """Analizza una singola immagine via callback OCR o pytesseract."""
    image_path = Path(image_path)
    if image_to_text is None:
        try:
            from PIL import Image
            import pytesseract
        except ImportError as exc:
            raise RuntimeError("PIL e pytesseract sono necessari per l'OCR immagini.") from exc

        image = Image.open(image_path).convert("L")
        ocr_text = pytesseract.image_to_string(image, lang=tesseract_lang)
    else:
        ocr_text = image_to_text(image_path)

    return analyze_ocr_text(ocr_text)


def process_hero_images(hero_name: str, image_files: list[str | Path], *, image_to_text=None) -> tuple[dict, int]:
    """Processa immagini associate a un eroe e restituisce dati combinati."""
    hero_data = dict(DEFAULT_STAT_VALUES)
    hero_data["talenti"] = []
    hero_data["rami_talenti_trovati"] = []
    defaults_used_count = 0
    stats_processed = False
    talents_processed = False

    related_images = [Path(path) for path in image_files if hero_name.lower() in Path(path).name.lower()]
    if not related_images:
        return hero_data, defaults_used_count

    for image_file in related_images:
        image_data, image_defaults_used = analyze_image(image_file, image_to_text=image_to_text)
        defaults_used_count += image_defaults_used

        if any(key in image_data for key in ("ATK", "HP", "DEF")) and not stats_processed:
            hero_data.update(image_data)
            stats_processed = True
        elif "talenti" in image_data and not talents_processed:
            hero_data["talenti"] = image_data.get("talenti", [])
            hero_data["rami_talenti_trovati"] = image_data.get("rami_talenti_trovati", [])
            if image_data.get("nome_completo_eroe"):
                hero_data["nome_completo_eroe"] = image_data["nome_completo_eroe"]
            talents_processed = True

        if stats_processed and talents_processed:
            break

    return hero_data, defaults_used_count


def save_hero_data_to_json(hero_data: dict, hero_name: str, output_dir: str | Path | None = None) -> Path:
    """Salva i dati estratti in JSON."""
    output_base = Path(output_dir) if output_dir is not None else DOOMSDAY_OCR_OUTPUT_DIR
    output_base.mkdir(parents=True, exist_ok=True)
    output_path = output_base / f"{hero_name}.json"
    output_path.write_text(json.dumps(hero_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path

