"""Load and query the versioned Doomsday domain registry."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Iterable
import unicodedata

from doomsday.intelligence.models import (
    ActionDefinition,
    AutomationPolicy,
    EvidenceClaim,
    EvidenceSource,
    GameModeDefinition,
    ObjectiveDefinition,
    RiskClass,
    RulesetDefinition,
)


ACTIVE_LIFECYCLES = {"active", "current", "contextual", "parallel"}


class DomainRegistry:
    """In-memory view of modes, rulesets, actions and supporting evidence."""

    def __init__(
        self,
        *,
        schema: str,
        registry_version: str,
        game_version: str,
        updated_at: str,
        modes: Iterable[GameModeDefinition],
        actions: Iterable[ActionDefinition],
        sources: Iterable[EvidenceSource],
        claims: Iterable[EvidenceClaim],
    ) -> None:
        self.schema = schema
        self.registry_version = registry_version
        self.game_version = game_version
        self.updated_at = updated_at
        self.modes = tuple(modes)
        self.actions = tuple(actions)
        self.sources = tuple(sources)
        self.claims = tuple(claims)
        self._modes_by_id = {item.mode_id: item for item in self.modes}
        self._actions_by_id = {item.action_id: item for item in self.actions}
        self._sources_by_id = {item.source_id: item for item in self.sources}
        self._claims_by_id = {item.claim_id: item for item in self.claims}
        self._rulesets_by_id = {
            ruleset.ruleset_id: ruleset
            for mode in self.modes
            for ruleset in mode.rulesets
        }

    @classmethod
    def load(cls, path: str | Path) -> "DomainRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "DomainRegistry":
        modes: list[GameModeDefinition] = []
        for mode_data in _dict_list(payload.get("modes")):
            mode_id = str(mode_data.get("mode_id", "")).strip()
            rulesets = tuple(
                _ruleset_from_dict(mode_id, ruleset_data)
                for ruleset_data in _dict_list(mode_data.get("rulesets"))
            )
            modes.append(
                GameModeDefinition(
                    mode_id=mode_id,
                    label=str(mode_data.get("label", mode_id)),
                    aliases=_strings(mode_data.get("aliases")),
                    mode_kind=str(mode_data.get("mode_kind", "activity")),
                    lifecycle=str(mode_data.get("lifecycle", "active")),
                    rulesets=rulesets,
                    notes=_notes(mode_data.get("notes")),
                )
            )

        actions = tuple(_action_from_dict(item) for item in _dict_list(payload.get("actions")))
        sources = tuple(_source_from_dict(item) for item in _dict_list(payload.get("sources")))
        claims = tuple(_claim_from_dict(item) for item in _dict_list(payload.get("claims")))
        return cls(
            schema=str(payload.get("schema", "")),
            registry_version=str(payload.get("registry_version", "")),
            game_version=str(payload.get("game_version", "")),
            updated_at=str(payload.get("updated_at", "")),
            modes=modes,
            actions=actions,
            sources=sources,
            claims=claims,
        )

    def get_mode(self, mode_id: str) -> GameModeDefinition | None:
        return self._modes_by_id.get(mode_id)

    def get_ruleset(self, ruleset_id: str) -> RulesetDefinition | None:
        return self._rulesets_by_id.get(ruleset_id)

    def get_action(self, action_id: str) -> ActionDefinition | None:
        return self._actions_by_id.get(action_id)

    def get_source(self, source_id: str) -> EvidenceSource | None:
        return self._sources_by_id.get(source_id)

    def get_claim(self, claim_id: str) -> EvidenceClaim | None:
        return self._claims_by_id.get(claim_id)

    def resolve_modes(
        self,
        query: str,
        *,
        game_version: str = "",
        include_inactive: bool = False,
        limit: int = 5,
    ) -> tuple[tuple[GameModeDefinition, float], ...]:
        normalized_query = _normalize(query)
        query_tokens = set(normalized_query.split())
        wants_legacy = bool(query_tokens & {"legacy", "vecchio", "precedente", "freedom"})
        scored: list[tuple[GameModeDefinition, float]] = []
        for mode in self.modes:
            ruleset = self.resolve_ruleset(mode.mode_id, game_version=game_version)
            currently_applicable = ruleset is not None
            if not include_inactive and not currently_applicable and not wants_legacy:
                continue
            names = (mode.label, mode.mode_id, *mode.aliases)
            score = max((_text_match_score(normalized_query, query_tokens, name) for name in names), default=0.0)
            if score <= 0:
                continue
            if mode.lifecycle in ACTIVE_LIFECYCLES:
                score += 5.0
            elif wants_legacy:
                score += 2.0
            else:
                score -= 25.0
            scored.append((mode, round(score, 4)))
        scored.sort(key=lambda item: (item[1], item[0].mode_id), reverse=True)
        return tuple(scored[:limit])

    def resolve_ruleset(self, mode_id: str, *, game_version: str = "") -> RulesetDefinition | None:
        mode = self.get_mode(mode_id)
        if not mode:
            return None
        target_version = game_version or self.game_version
        applicable = [
            item
            for item in mode.rulesets
            if _version_in_range(
                target_version,
                item.valid_from_game_version,
                item.valid_until_game_version,
            )
        ]
        if not applicable:
            return None
        applicable.sort(
            key=lambda item: (
                item.lifecycle in ACTIVE_LIFECYCLES,
                _version_tuple(item.valid_from_game_version),
                item.ruleset_id,
            ),
            reverse=True,
        )
        return applicable[0]

    def resolve_objective(self, ruleset: RulesetDefinition, query: str) -> ObjectiveDefinition | None:
        if not ruleset.objectives:
            return None
        normalized_query = _normalize(query)
        query_tokens = set(normalized_query.split())
        scored = []
        for index, objective in enumerate(ruleset.objectives):
            names = (objective.label, objective.objective_id, *objective.aliases)
            score = max((_text_match_score(normalized_query, query_tokens, name) for name in names), default=0.0)
            if index == 0:
                score += 0.01
            scored.append((score, objective))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def evidence_for_ruleset(self, ruleset: RulesetDefinition) -> tuple[EvidenceClaim, ...]:
        return tuple(
            claim
            for claim_id in ruleset.evidence_claim_ids
            if (claim := self.get_claim(claim_id)) is not None
        )

    def validate(self) -> tuple[str, ...]:
        issues: list[str] = []
        if self.schema != "doomsday.intelligence.domain.v1":
            issues.append(f"unsupported schema: {self.schema or '<missing>'}")
        issues.extend(_duplicates("mode_id", [item.mode_id for item in self.modes]))
        issues.extend(_duplicates("action_id", [item.action_id for item in self.actions]))
        issues.extend(_duplicates("source_id", [item.source_id for item in self.sources]))
        issues.extend(_duplicates("claim_id", [item.claim_id for item in self.claims]))
        ruleset_ids = [ruleset.ruleset_id for mode in self.modes for ruleset in mode.rulesets]
        issues.extend(_duplicates("ruleset_id", ruleset_ids))
        for mode in self.modes:
            if not mode.mode_id:
                issues.append("mode with empty mode_id")
            if not mode.rulesets:
                issues.append(f"mode without rulesets: {mode.mode_id}")
            for ruleset in mode.rulesets:
                if not ruleset.ruleset_id:
                    issues.append(f"mode with empty ruleset_id: {mode.mode_id}")
                for action_id in ruleset.workflow:
                    if action_id not in self._actions_by_id:
                        issues.append(f"unknown action {action_id} in {ruleset.ruleset_id}")
                for claim_id in ruleset.evidence_claim_ids:
                    if claim_id not in self._claims_by_id:
                        issues.append(f"unknown claim {claim_id} in {ruleset.ruleset_id}")
                for objective in ruleset.objectives:
                    if not objective.objective_id:
                        issues.append(f"objective with empty id in {ruleset.ruleset_id}")
        for action in self.actions:
            if not action.action_id:
                issues.append("action with empty action_id")
            if not action.effects:
                issues.append(f"action without machine-readable effects: {action.action_id}")
        for source in self.sources:
            if not source.source_id:
                issues.append("source with empty source_id")
        for claim in self.claims:
            if not claim.claim_id:
                issues.append("claim with empty claim_id")
            if claim.source_id not in self._sources_by_id:
                issues.append(f"unknown source {claim.source_id} for {claim.claim_id}")
        return tuple(issues)


def _ruleset_from_dict(mode_id: str, value: dict[str, Any]) -> RulesetDefinition:
    objectives = tuple(
        ObjectiveDefinition(
            objective_id=str(item.get("objective_id", "")),
            label=str(item.get("label", item.get("objective_id", ""))),
            aliases=_strings(item.get("aliases")),
            goal_facts=_mapping(item.get("goal_state")) or _mapping(item.get("goal_facts")),
            description=str(item.get("description", "")),
            goal_notes=_strings(item.get("goal_facts")),
        )
        for item in _dict_list(value.get("objectives"))
    )
    return RulesetDefinition(
        ruleset_id=str(value.get("ruleset_id", "")),
        mode_id=mode_id,
        label=str(value.get("label", value.get("ruleset_id", ""))),
        engine=str(value.get("engine", "unknown")),
        lifecycle=str(value.get("lifecycle", "active")),
        valid_from_game_version=_text(value.get("valid_from_game_version")),
        valid_until_game_version=_text(value.get("valid_until_game_version")),
        workflow=_strings(value.get("workflow")),
        objectives=objectives,
        constraints=tuple(_dict_list(value.get("constraint_facts"))) or tuple(_dict_list(value.get("constraints"))),
        success_facts=_mapping(value.get("success_state")) or _mapping(value.get("success_facts")),
        risk_class=_risk(value.get("risk_class")),
        evidence_claim_ids=_strings(value.get("evidence_claim_ids")),
        notes=_notes(value.get("notes")),
        constraint_notes=_strings(value.get("constraints")),
        success_notes=_strings(value.get("success_facts")),
    )


def _action_from_dict(value: dict[str, Any]) -> ActionDefinition:
    cost_value = value.get("cost", 1.0)
    cost_details = _mapping(cost_value)
    numeric_cost = float(cost_value) if isinstance(cost_value, (int, float)) else 1.0
    return ActionDefinition(
        action_id=str(value.get("action_id", "")),
        label=str(value.get("label", value.get("action_id", ""))),
        intents=_strings(value.get("intents")),
        preconditions=_mapping(value.get("precondition_facts")) or _mapping(value.get("preconditions")),
        effects=_mapping(value.get("effect_facts")) or _mapping(value.get("effects")),
        cost=numeric_cost,
        risk_class=_risk(value.get("risk_class")),
        automation_policy=_policy(value.get("automation_policy")),
        macro_intent=str(value.get("macro_intent") or ""),
        target_ui_node=str(value.get("target_ui_node") or ""),
        reversible=bool(value.get("reversible", True)),
        notes=_notes(value.get("notes")),
        precondition_notes=_strings(value.get("preconditions")),
        effect_notes=_strings(value.get("effects")),
        cost_details=cost_details,
    )


def _source_from_dict(value: dict[str, Any]) -> EvidenceSource:
    metadata = _mapping(value.get("metadata"))
    if value.get("trust_rank"):
        metadata = {**metadata, "trust_rank": value.get("trust_rank")}
    if value.get("freshness_policy"):
        metadata = {**metadata, "freshness_policy": value.get("freshness_policy")}
    raw_trust = value.get("trust_score")
    trust_score = float(raw_trust) if isinstance(raw_trust, (int, float)) else _trust_rank_score(value.get("trust_rank"))
    return EvidenceSource(
        source_id=str(value.get("source_id", "")),
        label=str(value.get("label", value.get("source_id", ""))),
        source_type=str(value.get("source_type", value.get("category", "unknown"))),
        uri=str(value.get("uri", value.get("url", ""))),
        trust_score=trust_score,
        retrieved_at=_text(value.get("retrieved_at")),
        observed_at=_text(value.get("observed_at")),
        locale=_text(value.get("locale")),
        applies_to_game_version=_text(value.get("applies_to_game_version")),
        metadata=metadata,
    )


def _claim_from_dict(value: dict[str, Any]) -> EvidenceClaim:
    return EvidenceClaim(
        claim_id=str(value.get("claim_id", "")),
        subject=str(value.get("subject", "")),
        predicate=str(value.get("predicate", "")),
        value=value.get("value", value.get("object")),
        confidence=float(value.get("confidence", 0.5)),
        source_id=str(value.get("source_id", "")),
        status=str(value.get("status", "observed")),
        valid_from_game_version=_text(value.get("valid_from_game_version")),
        valid_until_game_version=_text(value.get("valid_until_game_version")),
        valid_from=_text(value.get("valid_from")),
        valid_until=_text(value.get("valid_until")),
        supersedes=_strings(value.get("supersedes")),
        tags=_strings(value.get("tags")),
        notes=_notes(value.get("notes")),
        retrieved_at=_text(value.get("retrieved_at")),
        metadata=_mapping(value.get("metadata")),
    )


def _policy(value: Any) -> AutomationPolicy:
    aliases = {
        "auto_allowed": AutomationPolicy.AUTONOMOUS.value,
        "automatic": AutomationPolicy.AUTONOMOUS.value,
        "confirm": AutomationPolicy.CONFIRM_EACH.value,
        "advice_only": AutomationPolicy.SUGGEST_ONLY.value,
    }
    try:
        normalized = str(value or AutomationPolicy.SUGGEST_ONLY.value).strip().lower()
        return AutomationPolicy(aliases.get(normalized, normalized))
    except ValueError:
        return AutomationPolicy.SUGGEST_ONLY


def _risk(value: Any) -> RiskClass:
    aliases = {"read_only": RiskClass.LOW.value, "readonly": RiskClass.LOW.value}
    try:
        normalized = str(value or RiskClass.LOW.value).strip().lower()
        return RiskClass(aliases.get(normalized, normalized))
    except ValueError:
        return RiskClass.MEDIUM


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_like = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_like.lower()).strip()


def _text_match_score(normalized_query: str, query_tokens: set[str], candidate: str) -> float:
    normalized_candidate = _normalize(candidate)
    if not normalized_candidate:
        return 0.0
    if normalized_query == normalized_candidate:
        return 100.0
    if normalized_candidate in normalized_query:
        return 55.0 + min(20.0, len(normalized_candidate) / 3.0)
    candidate_tokens = set(normalized_candidate.split())
    overlap = query_tokens & candidate_tokens
    if not overlap:
        return 0.0
    return 12.0 * (len(overlap) / len(candidate_tokens)) + 6.0 * (len(overlap) / max(1, len(query_tokens)))


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(item) for item in re.findall(r"\d+", value or "")]
    return tuple(parts or [0])


def _version_in_range(version: str, lower: str, upper: str) -> bool:
    target = _version_tuple(version)
    if lower and target < _version_tuple(lower):
        return False
    if upper:
        upper_parts = _version_tuple(upper)
        if re.search(r"(?:^|[.])(?:x|\*)$", upper.strip(), flags=re.IGNORECASE):
            if target[: len(upper_parts)] > upper_parts:
                return False
        elif target > upper_parts:
            return False
    return True


def _duplicates(label: str, values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen:
            duplicates.append(f"duplicate {label}: {value}")
        seen.add(value)
    return duplicates


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _notes(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value or "")


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _trust_rank_score(value: Any) -> float:
    return {
        "authoritative": 0.95,
        "official": 0.9,
        "high": 0.8,
        "corroborating": 0.7,
        "community": 0.55,
        "advisory": 0.45,
        "unverified": 0.25,
    }.get(str(value or "").strip().lower(), 0.5)


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


__all__ = ["ACTIVE_LIFECYCLES", "DomainRegistry"]
