"""Confidence-aware state estimation that preserves unknown and conflicts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from doomsday.intelligence.models import GameState, Observation


@dataclass(frozen=True, slots=True)
class ObservationConflict:
    key: str
    values: tuple[object, ...]
    evidence_ids: tuple[str, ...]
    confidence_gap: float


@dataclass(frozen=True, slots=True)
class StateEstimate:
    state: GameState
    conflicts: tuple[ObservationConflict, ...]
    ignored_observations: tuple[Observation, ...]
    conflicting_observations: tuple[Observation, ...] = ()


class StateEstimator:
    def __init__(self, *, min_confidence: float = 0.6, conflict_margin: float = 0.1) -> None:
        self.min_confidence = max(0.0, min(1.0, min_confidence))
        self.conflict_margin = max(0.0, min(1.0, conflict_margin))

    def estimate(
        self,
        observations: Iterable[Observation],
        *,
        base_state: GameState | None = None,
    ) -> StateEstimate:
        base_state = base_state or GameState()
        grouped: dict[str, list[Observation]] = {}
        ignored: list[Observation] = []
        for observation in observations:
            if observation.confidence < self.min_confidence:
                ignored.append(observation)
                continue
            grouped.setdefault(observation.key, []).append(observation)

        facts = dict(base_state.facts)
        conflicts: list[ObservationConflict] = []
        conflicting_observations: list[Observation] = []
        accepted: list[Observation] = list(base_state.observations)
        for key, candidates in grouped.items():
            candidates.sort(key=lambda item: (item.confidence, item.observed_at), reverse=True)
            top = candidates[0]
            competing = next((item for item in candidates[1:] if item.value != top.value), None)
            if competing and (top.confidence - competing.confidence) <= self.conflict_margin:
                conflicts.append(
                    ObservationConflict(
                        key=key,
                        values=tuple(dict.fromkeys(_hashable_value(item.value) for item in candidates)),
                        evidence_ids=tuple(item.evidence_id for item in candidates if item.evidence_id),
                        confidence_gap=round(top.confidence - competing.confidence, 6),
                    )
                )
                if key not in base_state.facts:
                    facts.pop(key, None)
                # Keep disputed observations outside GameState: materializing that
                # state would otherwise choose one of them and silently turn a
                # conflict back into a fact.  They remain available on the
                # estimate for audit and later reconciliation.
                conflicting_observations.extend(candidates)
                continue
            if key not in base_state.facts:
                facts[key] = top.value
            accepted.append(top)

        return StateEstimate(
            state=GameState(
                facts=facts,
                observations=tuple(accepted),
                active_mode_id=base_state.active_mode_id,
                active_ruleset_id=base_state.active_ruleset_id,
                game_version=base_state.game_version,
            ),
            conflicts=tuple(conflicts),
            ignored_observations=tuple(ignored),
            conflicting_observations=tuple(conflicting_observations),
        )


def _hashable_value(value: object) -> object:
    if isinstance(value, list):
        return tuple(_hashable_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _hashable_value(item)) for key, item in value.items()))
    return value


__all__ = ["ObservationConflict", "StateEstimate", "StateEstimator"]
