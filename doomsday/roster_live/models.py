"""Modelli e validazione del roster live."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Any, Mapping


class SessionState(str, Enum):
    CAPTURING = "capturing"
    EXTRACTED = "extracted"
    PREVIEW_READY = "preview_ready"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    COMMITTED = "committed"
    FAILED = "failed"


class ChangeSetState(str, Enum):
    PREVIEW_READY = "preview_ready"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    COMMITTED = "committed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class ChangeDecision(str, Enum):
    UNRESOLVED = "unresolved"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_OVERRIDE = "manual_override"


INTEGER_FIELDS = {
    "level",
    "stars",
    "ATK",
    "DEF",
    "HP",
    "SPD",
    "Squadre",
    "EXP",
}
NUMBER_FIELDS = {"CRT", "CRTD", "ACC", "EVA", "EFF", "RES"}
TEXT_FIELDS = {"hero_name", "display_name", "rarity", "squad_type", "title"}
BOOLEAN_FIELDS = {"owned"}
STRUCTURED_FIELDS = {"skills", "skill_levels", "talents", "talent_branches"}
SUPPORTED_FIELDS = INTEGER_FIELDS | NUMBER_FIELDS | TEXT_FIELDS | BOOLEAN_FIELDS | STRUCTURED_FIELDS


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc(value: str, *, allow_future_seconds: int = 300) -> datetime:
    if not value:
        raise ValueError("Timestamp UTC obbligatorio.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Timestamp non valido: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError("Il timestamp deve includere il fuso orario.")
    parsed = parsed.astimezone(timezone.utc)
    if (parsed - datetime.now(timezone.utc)).total_seconds() > allow_future_seconds:
        raise ValueError("Il timestamp non può essere nel futuro.")
    return parsed


def normalize_hero_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")
    if not normalized:
        raise ValueError("Identità eroe non valida.")
    return normalized


def validate_field_value(field_name: str, value: Any) -> Any:
    if field_name not in SUPPORTED_FIELDS:
        raise ValueError(f"Campo roster non supportato: {field_name}")
    if field_name in INTEGER_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field_name} deve essere un intero non negativo.")
        if field_name == "stars" and value > 10:
            raise ValueError("stars fuori intervallo plausibile.")
    elif field_name in NUMBER_FIELDS:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"{field_name} deve essere un numero non negativo.")
    elif field_name in TEXT_FIELDS:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} deve contenere testo.")
        value = value.strip()
    elif field_name in BOOLEAN_FIELDS:
        if not isinstance(value, bool):
            raise ValueError(f"{field_name} deve essere booleano.")
    elif field_name in STRUCTURED_FIELDS:
        if not isinstance(value, (list, dict)) or not value:
            raise ValueError(f"{field_name} deve essere una struttura non vuota.")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def value_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    session_id: str
    stage: str
    hero_id: str
    path: str
    sha256: str
    width: int
    height: int
    captured_at: str
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class PreviewItem:
    item_id: str
    hero_id: str
    field_name: str
    current_value: Any
    proposed_value: Any
    confidence: float
    source_ref: str
    artifact_sha256: str
    conflict: bool
    alternatives: tuple[Mapping[str, Any], ...]
    decision: ChangeDecision
    override_value: Any = None
    decision_reason: str = ""


@dataclass(frozen=True, slots=True)
class ChangeSetPreview:
    change_set_id: str
    session_id: str
    base_revision: int
    state: ChangeSetState
    items: tuple[PreviewItem, ...]

    @property
    def unresolved_count(self) -> int:
        return sum(item.decision == ChangeDecision.UNRESOLVED for item in self.items)

    @property
    def conflict_count(self) -> int:
        return sum(item.conflict for item in self.items)


@dataclass(frozen=True, slots=True)
class CommitResult:
    change_set_id: str
    revision_id: int
    applied_items: int
    rejected_items: int
    outbox_items: int
    idempotent_replay: bool = False


__all__ = [
    "ArtifactRecord",
    "BOOLEAN_FIELDS",
    "ChangeDecision",
    "ChangeSetPreview",
    "ChangeSetState",
    "CommitResult",
    "INTEGER_FIELDS",
    "NUMBER_FIELDS",
    "PreviewItem",
    "STRUCTURED_FIELDS",
    "SUPPORTED_FIELDS",
    "SessionState",
    "TEXT_FIELDS",
    "canonical_json",
    "normalize_hero_id",
    "parse_utc",
    "utc_now_iso",
    "validate_field_value",
    "value_hash",
]
