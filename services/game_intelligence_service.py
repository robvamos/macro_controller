"""Stable application facade for the Doomsday intelligence core."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from core.paths import DOOMSDAY_DOMAIN_REGISTRY_PATH, DOOMSDAY_INTELLIGENCE_DB_PATH
from doomsday.intelligence.adapters import (
    NullActionBindingProvider,
    UIGraphMacroBindingProvider,
)
from doomsday.intelligence.models import GamePlan, GameState
from doomsday.intelligence.outcomes import OutcomeAssessment, OutcomeEvaluator
from doomsday.intelligence.persistence import IntelligenceRepository
from doomsday.intelligence.planner import WorkflowPlanner
from doomsday.intelligence.registry import DomainRegistry
from doomsday.intelligence.service import GameIntelligenceResult, GameIntelligenceService


def build_game_intelligence_service(
    *,
    registry_path: str | Path = DOOMSDAY_DOMAIN_REGISTRY_PATH,
    bind_macros: bool = False,
) -> GameIntelligenceService:
    registry = DomainRegistry.load(registry_path)
    issues = registry.validate()
    if issues:
        raise ValueError("Registry intelligence non valido: " + "; ".join(issues))
    binding_provider = UIGraphMacroBindingProvider() if bind_macros else NullActionBindingProvider()
    planner = WorkflowPlanner(registry, binding_provider=binding_provider)
    return GameIntelligenceService(registry, planner)


def plan_game_goal(
    query: str,
    *,
    facts: Mapping[str, Any] | None = None,
    game_version: str = "",
    bind_macros: bool = False,
    registry_path: str | Path = DOOMSDAY_DOMAIN_REGISTRY_PATH,
) -> GameIntelligenceResult:
    service = build_game_intelligence_service(
        registry_path=registry_path,
        bind_macros=bind_macros,
    )
    state = GameState(facts=dict(facts or {}), game_version=game_version)
    return service.plan_goal(query, state=state, game_version=game_version)


def record_game_episode(
    plan: GamePlan,
    *,
    status: str,
    executed_action_ids: Iterable[str],
    outcome: Mapping[str, Any] | None = None,
    durations_sec: Mapping[str, float] | None = None,
    evidence_refs: Iterable[str] = (),
    user_feedback: str = "",
    repository_path: str | Path = DOOMSDAY_INTELLIGENCE_DB_PATH,
) -> str:
    repository = IntelligenceRepository(repository_path)
    return repository.record_episode(
        plan,
        status=status,
        executed_action_ids=executed_action_ids,
        outcome=outcome,
        durations_sec=durations_sec,
        evidence_refs=evidence_refs,
        user_feedback=user_feedback,
    )


def evaluate_game_outcome(
    plan: GamePlan,
    *,
    executed_action_ids: Iterable[str],
    facts: Mapping[str, Any] | None = None,
    state: GameState | None = None,
) -> OutcomeAssessment:
    post_state = state or GameState(facts=dict(facts or {}))
    return OutcomeEvaluator().evaluate(
        plan,
        post_state=post_state,
        executed_action_ids=executed_action_ids,
    )


__all__ = [
    "build_game_intelligence_service",
    "evaluate_game_outcome",
    "plan_game_goal",
    "record_game_episode",
]
