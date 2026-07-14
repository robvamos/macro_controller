"""Parser OCR per statistiche eroe."""

from __future__ import annotations

import re

from doomsday.config import DEFAULT_STAT_VALUES


STAT_PATTERNS = {
    "ATK": r"\bATK\s*[:=]?\s*(\d+)\b",
    "DEF": r"\bDEF\s*[:=]?\s*(\d+)\b",
    "HP": r"\bHP\s*[:=]?\s*(\d+)\b",
    "Squadre": r"\b(?:Squadre|Teams)\s*[:=]?\s*(\d+)\b",
    "EXP": r"\bEXP\s*[:=]?\s*(\d+)\b",
    "SPD": r"\bSPD\s*[:=]?\s*(\d+)\b",
    "CRT": r"\bCRT\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
    "CRTD": r"\bCRTD\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
    "ACC": r"\bACC\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
    "EVA": r"\bEVA\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
    "EFF": r"\bEFF\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
    "RES": r"\bRES\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
}


def parse_stats_from_ocr(ocr_text: str, default_values: dict | None = None) -> tuple[dict, int]:
    """Estrae le statistiche principali da testo OCR.

    Restituisce `(stats, defaults_used_count)`.
    """
    if not ocr_text or not ocr_text.strip():
        return dict(DEFAULT_STAT_VALUES if default_values is None else default_values), len(STAT_PATTERNS)

    defaults = dict(DEFAULT_STAT_VALUES)
    if default_values:
        defaults.update(default_values)

    parsed = {}
    defaults_used = 0
    for stat_name, pattern in STAT_PATTERNS.items():
        match = re.search(pattern, ocr_text, flags=re.IGNORECASE)
        if match:
            raw_value = match.group(1)
            parsed[stat_name] = float(raw_value) if "." in raw_value else int(raw_value)
        else:
            parsed[stat_name] = defaults[stat_name]
            defaults_used += 1
    return parsed, defaults_used
