"""Map legacy Italian OCR parser keys into the canonical live-roster schema."""

from __future__ import annotations

from typing import Any, Mapping


OCR_FIELD_ALIASES = {
    "nome_completo_eroe": "display_name",
    "talenti": "talents",
    "rami_talenti_trovati": "talent_branches",
}


def canonicalize_ocr_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    canonical = {}
    for key, value in fields.items():
        target = OCR_FIELD_ALIASES.get(key, key)
        if target in canonical and canonical[target] != value:
            raise ValueError(f"Conflicting OCR values for canonical field {target}")
        canonical[target] = value
    return canonical


__all__ = ["OCR_FIELD_ALIASES", "canonicalize_ocr_fields"]
