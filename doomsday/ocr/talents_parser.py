"""Parser OCR per talenti eroe."""

from __future__ import annotations

import re
import unicodedata

from doomsday.config import DEFAULT_TALENT_BRANCHES


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def parse_talents_from_ocr(raw_text: str, known_branches: list[str] | None = None) -> dict:
    """Estrae nome eroe, rami e talenti da testo OCR grezzo."""
    lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
    branches = known_branches or DEFAULT_TALENT_BRANCHES
    normalized_branches = {_normalize_text(branch): branch for branch in branches}

    parsed_data = {
        "nome_completo_eroe": None,
        "talenti": [],
        "rami_talenti_trovati": [],
    }

    hero_name_candidate = None
    for line in reversed(lines[-7:]):
        normalized_line = _normalize_text(line)
        if re.search(r"\d+\s*/\s*\d+", line):
            continue
        if any(branch in normalized_line for branch in normalized_branches):
            continue
        cleaned = re.sub(r"[^0-9A-Za-zÀ-ÿ\s'\-]", "", line).strip()
        if cleaned and len(cleaned.split()) >= 2:
            hero_name_candidate = cleaned
            break
    parsed_data["nome_completo_eroe"] = hero_name_candidate

    current_branch = "Sconosciuto"
    for line in lines:
        normalized_line = _normalize_text(line)
        for normalized_branch, original_branch in normalized_branches.items():
            if normalized_branch in normalized_line:
                current_branch = original_branch.title()
                if current_branch not in parsed_data["rami_talenti_trovati"]:
                    parsed_data["rami_talenti_trovati"].append(current_branch)
                break

        match = re.search(r"^([^0-9\W_].+?)\s*(\d+)\s*/\s*(\d+)(.*)$", line)
        if not match:
            continue

        talent_name = match.group(1).strip()
        if len(talent_name) < 2:
            continue
        parsed_data["talenti"].append(
            {
                "nome_talento": talent_name,
                "ramo": current_branch,
                "livello_attuale": int(match.group(2)),
                "livello_massimo": int(match.group(3)),
                "description_at_this_level": match.group(4).strip(),
            }
        )

    return parsed_data

