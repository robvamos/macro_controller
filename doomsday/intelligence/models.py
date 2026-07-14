"""Canonical domain models for game understanding, planning and evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Mapping


JSONValue = Any


class AutomationPolicy(str, Enum):
    """How far the application may go without explicit user involvement."""

    AUTONOMOUS = "autonomous"
    CONFIRM_EACH = "confirm_each"
    SUGGEST_ONLY = "suggest_only"
    MANUAL = "manual"


class RiskClass(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    source_id: str
    label: str
    source_type: str
    uri: str = ""
    trust_score: float = 0.5
    retrieved_at: str = ""
    observed_at: str = ""
    locale: str = ""
    applies_to_game_version: str = ""
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if not 0.0 <= self.trust_score <= 1.0:
            raise ValueError("trust_score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class EvidenceClaim:
    claim_id: str
    subject: str
    predicate: str
    value: JSONValue
    confidence: float
    source_id: str
    status: str = "observed"
    valid_from_game_version: str = ""
    valid_until_game_version: str = ""
    valid_from: str = ""
    valid_until: str = ""
    supersedes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    notes: str = ""
    retrieved_at: str = ""
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.claim_id.strip():
            raise ValueError("claim_id is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("claim confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class Observation:
    key: str
    value: JSONValue
    confidence: float = 1.0
    source_id: str = "runtime"
    observed_at: str = ""
    evidence_id: str = ""
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("observation key is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("observation confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ObjectiveDefinition:
    objective_id: str
    label: str
    aliases: tuple[str, ...]
    goal_facts: Mapping[str, JSONValue]
    description: str = ""
    goal_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    action_id: str
    label: str
    intents: tuple[str, ...]
    preconditions: Mapping[str, JSONValue]
    effects: Mapping[str, JSONValue]
    cost: float = 1.0
    risk_class: RiskClass = RiskClass.LOW
    automation_policy: AutomationPolicy = AutomationPolicy.SUGGEST_ONLY
    macro_intent: str = ""
    target_ui_node: str = ""
    reversible: bool = True
    notes: str = ""
    precondition_notes: tuple[str, ...] = ()
    effect_notes: tuple[str, ...] = ()
    cost_details: Mapping[str, JSONValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RulesetDefinition:
    ruleset_id: str
    mode_id: str
    label: str
    engine: str
    lifecycle: str
    valid_from_game_version: str
    valid_until_game_version: str
    workflow: tuple[str, ...]
    objectives: tuple[ObjectiveDefinition, ...]
    constraints: tuple[Mapping[str, JSONValue], ...]
    success_facts: Mapping[str, JSONValue]
    risk_class: RiskClass
    evidence_claim_ids: tuple[str, ...]
    notes: str = ""
    constraint_notes: tuple[str, ...] = ()
    success_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GameModeDefinition:
    mode_id: str
    label: str
    aliases: tuple[str, ...]
    mode_kind: str
    lifecycle: str
    rulesets: tuple[RulesetDefinition, ...]
    notes: str = ""


@dataclass(frozen=True, slots=True)
class GameState:
    """Current known facts; observations retain confidence and provenance."""

    facts: Mapping[str, JSONValue] = field(default_factory=dict)
    observations: tuple[Observation, ...] = ()
    active_mode_id: str = ""
    active_ruleset_id: str = ""
    game_version: str = ""

    def value(self, key: str, default: JSONValue = None) -> JSONValue:
        if key in self.facts:
            return self.facts[key]
        candidates = [item for item in self.observations if item.key == key]
        if not candidates:
            return default
        candidates.sort(key=lambda item: (item.confidence, item.observed_at), reverse=True)
        return candidates[0].value

    def materialize(self) -> dict[str, JSONValue]:
        materialized = dict(self.facts)
        explicit_keys = set(materialized)
        for observation in sorted(self.observations, key=lambda item: item.confidence):
            if observation.confidence >= 0.5 and observation.key not in explicit_keys:
                materialized[observation.key] = observation.value
        return materialized


@dataclass(frozen=True, slots=True)
class GoalInterpretation:
    query: str
    mode_id: str
    ruleset_id: str
    objective_id: str
    confidence: float
    alternatives: tuple[str, ...] = ()
    needs_context: bool = False
    assumptions: tuple[str, ...] = ()
    constraints: Mapping[str, JSONValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActionBinding:
    action_id: str
    binding_type: str
    binding_id: str
    label: str
    confidence: float = 1.0
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlanStep:
    index: int
    action_id: str
    label: str
    status: str
    reason: str
    risk_class: RiskClass
    automation_policy: AutomationPolicy
    preconditions: Mapping[str, JSONValue]
    expected_effects: Mapping[str, JSONValue]
    macro_intent: str = ""
    target_ui_node: str = ""
    binding: ActionBinding | None = None


@dataclass(frozen=True, slots=True)
class GamePlan:
    plan_id: str
    query: str
    mode_id: str
    ruleset_id: str
    objective_id: str
    created_at: str
    steps: tuple[PlanStep, ...]
    initial_facts: Mapping[str, JSONValue]
    projected_facts: Mapping[str, JSONValue]
    success_facts: Mapping[str, JSONValue]
    blocked: bool = False
    blocking_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_iso_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def to_primitive(value: Any) -> Any:
    """Convert nested dataclasses/enums into JSON-serializable primitives."""

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return to_primitive(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [to_primitive(item) for item in value]
    return value


__all__ = [
    "ActionBinding",
    "ActionDefinition",
    "AutomationPolicy",
    "EvidenceClaim",
    "EvidenceSource",
    "GameModeDefinition",
    "GamePlan",
    "GameState",
    "GoalInterpretation",
    "ObjectiveDefinition",
    "Observation",
    "PlanStep",
    "RiskClass",
    "RulesetDefinition",
    "parse_iso_date",
    "to_primitive",
    "utc_now_iso",
]
