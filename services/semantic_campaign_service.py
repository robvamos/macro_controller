"""Semantic attribution for learning sequences, macros and game operations.

This layer records why a macro exists without granting it permission to execute.
One macro can support several campaigns, while every use remains versioned and
must be independently validated by a person and by post-action evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from core.paths import DOOMSDAY_INTELLIGENCE_DB_PATH
from doomsday.intelligence.persistence import IntelligenceRepository
from repositories.macro_repository import get_all_macros, get_macro_metadata_by_id, load_macro_events


CAMPAIGN_KINDS = (
    "field_battle",
    "event_operation",
    "campaign_progression",
    "roster_management",
    "base_operation",
    "resource_operation",
    "research_development",
)

ASSET_DOMAINS = (
    "commanders",
    "heroes",
    "vehicles",
    "beasts",
    "weapons",
    "armaments",
    "troops",
    "formations",
    "resources",
)

OPERATION_TAGS = (
    "battle",
    "march",
    "deploy",
    "rally",
    "event",
    "challenge",
    "campaign",
    "upgrade",
    "equipment",
    "beast_support",
    "weapon_upgrade",
    "vehicle_upgrade",
    "commander_management",
    "roster_review",
    "collection",
)


def create_semantic_campaign(
    *,
    label: str,
    campaign_kind: str,
    objective: str,
    operation_tags: Iterable[str] = (),
    asset_domains: Iterable[str] = (),
    game_version: str = "",
    notes: str = "",
    repository_path: str | Path = DOOMSDAY_INTELLIGENCE_DB_PATH,
) -> str:
    if not label.strip() or not objective.strip():
        raise ValueError("Campagna e obiettivo sono obbligatori.")
    _validate_values("campaign_kind", (campaign_kind,), CAMPAIGN_KINDS)
    normalized_tags = _normalize_values(operation_tags)
    normalized_assets = _normalize_values(asset_domains)
    _validate_values("operation_tag", normalized_tags, OPERATION_TAGS)
    _validate_values("asset_domain", normalized_assets, ASSET_DOMAINS)
    return IntelligenceRepository(repository_path).create_campaign(
        label=label.strip(),
        campaign_kind=campaign_kind,
        objective=objective.strip(),
        operation_tags=normalized_tags,
        asset_domains=normalized_assets,
        game_version=game_version.strip(),
        notes=notes.strip(),
    )


def attribute_macro_to_campaign(
    *,
    campaign_id: str,
    macro_id: int,
    operation_id: str,
    relation_type: str = "candidate",
    confidence: float = 0.0,
    validation_status: str = "unverified",
    notes: str = "",
    repository_path: str | Path = DOOMSDAY_INTELLIGENCE_DB_PATH,
) -> dict[str, Any]:
    macro = get_macro_metadata_by_id(int(macro_id))
    if macro is None:
        raise ValueError(f"Macro non trovata: {macro_id}")
    if not operation_id.strip():
        raise ValueError("L'operazione semantica e' obbligatoria.")
    if validation_status not in {"unverified", "human_reviewed", "validated", "retired"}:
        raise ValueError(f"Stato di validazione non supportato: {validation_status}")
    repository = IntelligenceRepository(repository_path)
    binding_id = repository.bind_campaign_macro(
        campaign_id=campaign_id,
        macro_id=int(macro_id),
        operation_id=operation_id.strip(),
        relation_type=relation_type,
        confidence=confidence,
        validation_status=validation_status,
        notes=notes.strip(),
    )
    events = load_macro_events(int(macro_id))
    evidence_id = repository.record_campaign_sequence_evidence(
        campaign_id=campaign_id,
        macro_id=int(macro_id),
        sequence_hash=sequence_hash(events),
        event_count=len(events),
        ui_nodes=sorted({str(event["ui_node_id"]) for event in events if event.get("ui_node_id")}),
        element_ids=sorted({int(event["game_element_id"]) for event in events if event.get("game_element_id") is not None}),
        notes="Snapshot della sequenza al momento dell'attribuzione; non costituisce prova di esito.",
    )
    return {
        "binding_id": binding_id,
        "evidence_id": evidence_id,
        "macro_id": int(macro_id),
        "macro_name": macro.get("nome", ""),
        "operation_id": operation_id.strip(),
    }


def list_semantic_campaigns(*, repository_path: str | Path = DOOMSDAY_INTELLIGENCE_DB_PATH) -> tuple[dict[str, Any], ...]:
    repository = IntelligenceRepository(repository_path)
    campaigns = []
    for campaign in repository.list_campaigns():
        bindings = repository.list_campaign_macro_bindings(campaign_id=campaign["campaign_id"])
        runs = repository.list_campaign_runs(campaign_id=campaign["campaign_id"])
        campaigns.append({
            **campaign,
            "macro_bindings": bindings,
            "runs": runs,
            "coverage": _campaign_coverage(bindings, runs),
        })
    return tuple(campaigns)


def record_campaign_run(
    *,
    campaign_id: str,
    operation_id: str,
    status: str,
    macro_id: int | None = None,
    pre_state: dict[str, Any] | None = None,
    post_state: dict[str, Any] | None = None,
    evidence_refs: Iterable[str] = (),
    user_feedback: str = "",
    repository_path: str | Path = DOOMSDAY_INTELLIGENCE_DB_PATH,
) -> str:
    """Persist a supervised observation; it never promotes a macro automatically."""
    if not operation_id.strip():
        raise ValueError("L'operazione semantica e' obbligatoria.")
    if macro_id is not None and get_macro_metadata_by_id(int(macro_id)) is None:
        raise ValueError(f"Macro non trovata: {macro_id}")
    return IntelligenceRepository(repository_path).record_campaign_run(
        campaign_id=campaign_id,
        macro_id=macro_id,
        operation_id=operation_id.strip(),
        status=status,
        pre_state=pre_state,
        post_state=post_state,
        evidence_refs=evidence_refs,
        user_feedback=user_feedback.strip(),
    )


def suggest_campaign_attributions(*, repository_path: str | Path = DOOMSDAY_INTELLIGENCE_DB_PATH) -> tuple[dict[str, Any], ...]:
    """Return explainable candidates only; a person still creates every binding."""
    campaigns = list_semantic_campaigns(repository_path=repository_path)
    assigned_ids = {binding["macro_id"] for campaign in campaigns for binding in campaign["macro_bindings"]}
    suggestions = []
    for macro in get_all_macros():
        if macro.get("macro_kind") == "system" or int(macro["id"]) in assigned_ids:
            continue
        tokens = _tokens(" ".join(str(macro.get(key, "")) for key in ("nome", "descrizione")))
        best = None
        for campaign in campaigns:
            campaign_tokens = _tokens(" ".join((campaign["label"], campaign["objective"], *campaign["operation_tags"], *campaign["asset_domains"])))
            overlap = tokens & campaign_tokens
            if not overlap:
                continue
            candidate = (len(overlap), campaign, sorted(overlap))
            if best is None or candidate[0] > best[0]:
                best = candidate
        if best:
            score, campaign, overlap = best
            suggestions.append({
                "macro_id": int(macro["id"]),
                "macro_name": macro.get("nome", ""),
                "campaign_id": campaign["campaign_id"],
                "campaign_label": campaign["label"],
                "confidence": round(min(0.5, 0.15 * score), 2),
                "matched_terms": tuple(overlap),
                "reason": "Corrispondenza lessicale, richiede revisione umana.",
            })
    return tuple(sorted(suggestions, key=lambda item: (-item["confidence"], item["macro_name"])))


def sequence_hash(events: Iterable[dict[str, Any]]) -> str:
    """Stable content signature; coordinates stay evidence, never a semantic label."""
    compact = [
        {
            "type": event.get("type"),
            "event": event.get("event"),
            "name": event.get("name"),
            "button": event.get("button"),
            "ui_node_id": event.get("ui_node_id"),
            "game_element_id": event.get("game_element_id"),
        }
        for event in events
    ]
    payload = json.dumps(compact, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_values(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _validate_values(label: str, values: Iterable[str], allowed: Iterable[str]) -> None:
    allowed_values = set(allowed)
    unknown = sorted(set(values) - allowed_values)
    if unknown:
        raise ValueError(f"{label} non riconosciuti: {', '.join(unknown)}")


def _campaign_coverage(bindings: Iterable[dict[str, Any]], runs: Iterable[dict[str, Any]]) -> dict[str, int]:
    binding_list = tuple(bindings)
    run_list = tuple(runs)
    return {
        "macro_bindings": len(binding_list),
        "validated_bindings": sum(item["validation_status"] == "validated" for item in binding_list),
        "observed_runs": len(run_list),
        "successful_runs": sum(item["status"] == "observed_success" for item in run_list),
    }


def _tokens(value: str) -> set[str]:
    return {item.casefold() for item in value.replace("_", " ").replace("-", " ").split() if len(item) > 2}


__all__ = [
    "ASSET_DOMAINS",
    "CAMPAIGN_KINDS",
    "OPERATION_TAGS",
    "attribute_macro_to_campaign",
    "create_semantic_campaign",
    "list_semantic_campaigns",
    "record_campaign_run",
    "sequence_hash",
    "suggest_campaign_attributions",
]
