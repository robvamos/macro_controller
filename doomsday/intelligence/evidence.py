"""Atomic provider contributions and conflict-preserving evidence resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from typing import Any, Callable, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class ProviderContribution:
    """Compatible with the shared doomsday-crawler-support contribution shape."""

    provider_id: str
    provider_type: str
    subject_id: str
    field_name: str
    field_value: Any
    confidence: float
    observed_at: str
    source_ref: str
    trust_score: float = 0.5
    game_version: str = ""
    server_scope: str = ""
    normalization_notes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider_id or not self.subject_id or not self.field_name:
            raise ValueError("provider_id, subject_id and field_name are required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not 0.0 <= self.trust_score <= 1.0:
            raise ValueError("trust_score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ResolutionAlternative:
    value: Any
    score: float
    contribution_count: int
    provider_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClaimResolution:
    subject_id: str
    field_name: str
    selected_value: Any
    confidence: float
    alternatives: tuple[ResolutionAlternative, ...]
    conflicts: bool
    contribution_count: int
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceAccessPolicy:
    source_type: str
    read_only: bool
    requires_human_activation: bool
    persist_credentials: bool
    persist_raw_content: bool
    scope_required: bool
    notes: str


DISCORD_ACCESS_POLICY = SourceAccessPolicy(
    source_type="discord-authenticated",
    read_only=True,
    requires_human_activation=True,
    persist_credentials=False,
    persist_raw_content=False,
    scope_required=True,
    notes=(
        "Usare solo tab scelti dall'utente e canali allowlisted; conservare claim, permalink, "
        "autore/canale/timestamp necessari alla provenienza, non cookie o dump indiscriminati."
    ),
)


class EvidenceResolver:
    """Resolve one field while retaining every competing value and source."""

    def __init__(
        self,
        *,
        trust_resolver: Callable[[ProviderContribution], float] | None = None,
        freshness_half_life_days: float = 365.0,
    ) -> None:
        self.trust_resolver = trust_resolver
        self.freshness_half_life_days = max(1.0, freshness_half_life_days)

    def resolve(self, contributions: Iterable[ProviderContribution]) -> ClaimResolution:
        items = tuple(contributions)
        if not items:
            raise ValueError("at least one contribution is required")
        subjects = {(item.subject_id, item.field_name) for item in items}
        if len(subjects) != 1:
            raise ValueError("all contributions must describe the same subject field")

        grouped: dict[str, list[ProviderContribution]] = {}
        values: dict[str, Any] = {}
        for item in items:
            key = _canonical_value(item.field_value)
            grouped.setdefault(key, []).append(item)
            values[key] = item.field_value

        alternatives: list[ResolutionAlternative] = []
        for key, group in grouped.items():
            score = sum(self._weight(item) for item in group)
            alternatives.append(
                ResolutionAlternative(
                    value=values[key],
                    score=round(score, 6),
                    contribution_count=len(group),
                    provider_ids=tuple(sorted({item.provider_id for item in group})),
                )
            )
        alternatives.sort(key=lambda item: (item.score, item.contribution_count), reverse=True)
        total_score = sum(max(0.0, item.score) for item in alternatives)
        selected = alternatives[0]
        confidence = selected.score / total_score if total_score else 0.0
        notes = []
        if len(alternatives) > 1:
            notes.append("Sono presenti valori in conflitto; nessuna evidenza è stata scartata.")
        if any(not item.game_version for item in items):
            notes.append("Alcuni contributi non dichiarano la versione del gioco.")
        return ClaimResolution(
            subject_id=items[0].subject_id,
            field_name=items[0].field_name,
            selected_value=selected.value,
            confidence=round(max(0.0, min(1.0, confidence)), 6),
            alternatives=tuple(alternatives),
            conflicts=len(alternatives) > 1,
            contribution_count=len(items),
            notes=tuple(notes),
        )

    def _weight(self, contribution: ProviderContribution) -> float:
        trust = contribution.trust_score
        if self.trust_resolver is not None:
            trust = max(0.0, min(1.0, float(self.trust_resolver(contribution))))
        freshness = _freshness_weight(contribution.observed_at, self.freshness_half_life_days)
        return contribution.confidence * trust * freshness


def _canonical_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _freshness_weight(observed_at: str, half_life_days: float) -> float:
    if not observed_at:
        return 0.75
    try:
        parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.75
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400.0)
    return math.pow(0.5, age_days / half_life_days)


__all__ = [
    "ClaimResolution",
    "DISCORD_ACCESS_POLICY",
    "EvidenceResolver",
    "ProviderContribution",
    "ResolutionAlternative",
    "SourceAccessPolicy",
]
