"""Servizi di lettura per le marce campo Doomsday."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIELD_PAIRS_PATH = PROJECT_ROOT / "data" / "doomsday" / "roster" / "field_pairs.json"


def load_field_roster(path: str | Path | None = None) -> dict[str, Any]:
    """Carica il documento strutturato con assetto attuale e proposta."""
    roster_path = Path(path) if path else DEFAULT_FIELD_PAIRS_PATH
    if not roster_path.exists():
        return {
            "version": 1,
            "updated_at": None,
            "context": "Nessun roster campo configurato.",
            "current_pairs": [],
            "recommended_pairs": [],
            "bench_and_development": [],
            "development_plan": [],
        }
    with roster_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return normalize_field_roster(data)


def normalize_field_roster(data: dict[str, Any]) -> dict[str, Any]:
    """Applica default minimi per rendere stabile la UI."""
    normalized = dict(data)
    normalized.setdefault("version", 1)
    normalized.setdefault("updated_at", None)
    normalized.setdefault("context", "")
    normalized.setdefault("current_pairs", [])
    normalized.setdefault("recommended_pairs", [])
    normalized.setdefault("bench_and_development", [])
    normalized.setdefault("development_plan", [])
    return normalized


def pair_row(pair: dict[str, Any]) -> tuple[Any, ...]:
    """Restituisce i valori principali di una marcia per Treeview."""
    return (
        pair.get("slot", ""),
        pair.get("front_hero", ""),
        pair.get("back_hero", ""),
        pair.get("front_beast", ""),
        pair.get("support_beast", ""),
        pair.get("role", ""),
    )


def pair_title(pair: dict[str, Any]) -> str:
    slot = pair.get("slot", "")
    label = pair.get("label") or pair.get("role") or "Marcia"
    front = pair.get("front_hero", "?")
    back = pair.get("back_hero", "?")
    prefix = f"{slot}. " if slot != "" else ""
    return f"{prefix}{label}: {front} + {back}"


def format_pair_details(pair: dict[str, Any]) -> str:
    """Formatta i dettagli di una coppia in testo leggibile."""
    if not pair:
        return "Seleziona una marcia per vedere i dettagli."

    weapons = pair.get("special_weapons") or {}
    lines = [
        pair_title(pair),
        "",
        f"Eroi: {pair.get('front_hero', '?')} davanti, {pair.get('back_hero', '?')} dietro",
        f"Bestie: {pair.get('front_beast', '?')} davanti, {pair.get('support_beast', '?')} supporto",
        f"Ruolo: {pair.get('role', '-')}",
        f"Arma speciale davanti: {weapons.get('front_hero', 'non specificata')}",
        f"Arma speciale dietro: {weapons.get('back_hero', 'non specificata')}",
    ]
    for key, title in (
        ("strengths", "Punti forti"),
        ("concerns", "Rischi"),
    ):
        values = pair.get(key) or []
        if values:
            lines.append(f"{title}: {', '.join(values)}")
    for key, title in (
        ("priority", "Priorita"),
        ("why", "Perche"),
        ("tradeoff", "Scambio"),
        ("notes", "Note"),
    ):
        value = pair.get(key)
        if value:
            lines.append(f"{title}: {value}")
    return "\n".join(lines)


def format_bench_and_plan(roster: dict[str, Any]) -> str:
    """Restituisce panchina, sviluppo e piano operativo in forma compatta."""
    lines: list[str] = []
    bench = roster.get("bench_and_development") or []
    if bench:
        lines.append("In sviluppo / panchina")
        for item in bench:
            lines.append(
                f"- {item.get('name', '?')}: {item.get('status', '-')}; "
                f"arma {item.get('special_weapon', '-')}; {item.get('recommendation', '')}"
            )
    plan = roster.get("development_plan") or []
    if plan:
        if lines:
            lines.append("")
        lines.append("Piano di sviluppo")
        for index, step in enumerate(plan, start=1):
            lines.append(f"{index}. {step}")
    return "\n".join(lines)
