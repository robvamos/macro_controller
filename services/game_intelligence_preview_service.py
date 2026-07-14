"""View model read-only per presentare un piano semantico nella GUI."""

from __future__ import annotations

import json
from typing import Any, Mapping

from services.game_intelligence_service import plan_game_goal


def parse_preview_facts(raw_facts: str) -> dict[str, Any]:
    """Legge un oggetto JSON opzionale senza introdurre stato o scritture."""
    if not raw_facts.strip():
        return {}
    parsed = json.loads(raw_facts)
    if not isinstance(parsed, dict):
        raise ValueError("I fatti devono essere un oggetto JSON, ad esempio {\"ui.observed\": true}.")
    return parsed


def build_game_plan_preview(
    goal: str,
    *,
    game_version: str = "",
    raw_facts: str = "",
) -> dict[str, Any]:
    """Costruisce una preview consultiva; non collega né esegue macro."""
    if not goal.strip():
        raise ValueError("Inserisci un obiettivo di gioco.")
    result = plan_game_goal(
        goal.strip(),
        facts=parse_preview_facts(raw_facts),
        game_version=game_version.strip(),
        bind_macros=False,
    )
    return result.to_dict()


def format_game_plan_summary(preview: Mapping[str, Any]) -> str:
    """Restituisce il riepilogo leggibile della sola interpretazione e del piano."""
    interpretation = preview.get("interpretation", {})
    plan = preview.get("plan", {})
    confidence = float(interpretation.get("confidence", 0.0)) * 100
    lines = [
        f"Modalita: {interpretation.get('mode_id') or 'da confermare'}",
        f"Ruleset: {interpretation.get('ruleset_id') or 'non disponibile'}",
        f"Obiettivo: {interpretation.get('objective_id') or 'non riconosciuto'}",
        f"Confidenza: {confidence:.0f}%",
        f"Stato: {'bloccato' if plan.get('blocked') else 'consultivo'}",
    ]
    assumptions = interpretation.get("assumptions") or []
    warnings = plan.get("warnings") or []
    blockers = plan.get("blocking_reasons") or []
    if assumptions:
        lines.append("Assunzioni: " + "; ".join(str(item) for item in assumptions))
    if blockers:
        lines.append("Blocchi: " + "; ".join(str(item) for item in blockers))
    if warnings:
        lines.append("Avvisi: " + "; ".join(str(item) for item in warnings))
    return "\n".join(lines)


def plan_step_rows(preview: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    """Adatta i passi del piano a righe stabili per una Treeview."""
    rows = []
    for step in preview.get("plan", {}).get("steps", []):
        rows.append(
            (
                step.get("index", ""),
                step.get("label", ""),
                step.get("status", ""),
                step.get("risk_class", ""),
                step.get("automation_policy", ""),
            )
        )
    return rows


def format_plan_step_details(preview: Mapping[str, Any], row_index: int) -> str:
    """Formatta un singolo passo senza esporre coordinate o comandi eseguibili."""
    steps = preview.get("plan", {}).get("steps", [])
    if row_index < 0 or row_index >= len(steps):
        return "Seleziona un passo per vedere i dettagli."
    step = steps[row_index]
    lines = [
        str(step.get("label", "Passo")),
        "",
        f"Stato: {step.get('status', '-')}",
        f"Rischio: {step.get('risk_class', '-')}",
        f"Policy: {step.get('automation_policy', '-')}",
        f"Motivo: {step.get('reason', '-')}",
    ]
    preconditions = step.get("preconditions") or {}
    effects = step.get("expected_effects") or {}
    if preconditions:
        lines.append("Precondizioni: " + json.dumps(preconditions, ensure_ascii=False, sort_keys=True))
    if effects:
        lines.append("Effetti previsti: " + json.dumps(effects, ensure_ascii=False, sort_keys=True))
    return "\n".join(lines)


__all__ = [
    "build_game_plan_preview",
    "format_game_plan_summary",
    "format_plan_step_details",
    "parse_preview_facts",
    "plan_step_rows",
]
