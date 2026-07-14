"""Application service for intent interpretation, planning and safe adaptation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping
import unicodedata

from doomsday.intelligence.models import (
    GamePlan,
    GameState,
    GoalInterpretation,
    to_primitive,
)
from doomsday.intelligence.planner import WorkflowPlanner
from doomsday.intelligence.registry import DomainRegistry


@dataclass(frozen=True, slots=True)
class GameIntelligenceResult:
    interpretation: GoalInterpretation
    plan: GamePlan
    registry_version: str
    game_version: str
    evidence_claim_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


class GameIntelligenceService:
    def __init__(self, registry: DomainRegistry, planner: WorkflowPlanner | None = None) -> None:
        self.registry = registry
        self.planner = planner or WorkflowPlanner(registry)

    def interpret_goal(
        self,
        query: str,
        *,
        state: GameState | None = None,
        game_version: str = "",
    ) -> GoalInterpretation:
        if not query.strip():
            raise ValueError("query cannot be empty")
        state = state or GameState()
        selected_version = game_version or state.game_version or self.registry.game_version
        constraints = _extract_constraints(query)
        candidates = self.registry.resolve_modes(query, game_version=selected_version, limit=5)

        mode = None
        top_score = 0.0
        alternatives: tuple[str, ...] = ()
        if state.active_mode_id:
            active_mode = self.registry.get_mode(state.active_mode_id)
            if active_mode is not None:
                mode = active_mode
                top_score = 90.0
        if mode is None and candidates:
            mode, top_score = candidates[0]
            alternatives = tuple(item.mode_id for item, _ in candidates[1:])
        if mode is None:
            mode = next(
                (
                    self.registry.get_mode(mode_id)
                    for mode_id in ("context.discovery", "challenge_context", "campaign_hub")
                    if self.registry.get_mode(mode_id) is not None
                ),
                None,
            )
            top_score = 20.0 if mode else 0.0
        if mode is None:
            empty = GoalInterpretation(
                query=query,
                mode_id="",
                ruleset_id="",
                objective_id="",
                confidence=0.0,
                alternatives=(),
                needs_context=True,
                assumptions=("Nessuna modalità compatibile presente nel registry.",),
                constraints=constraints,
            )
            return empty

        ruleset = None
        if state.active_ruleset_id:
            candidate_ruleset = self.registry.get_ruleset(state.active_ruleset_id)
            if candidate_ruleset and candidate_ruleset.mode_id == mode.mode_id:
                ruleset = candidate_ruleset
        ruleset = ruleset or self.registry.resolve_ruleset(mode.mode_id, game_version=selected_version)
        objective = self.registry.resolve_objective(ruleset, query) if ruleset else None
        close_alternative = bool(
            len(candidates) > 1 and candidates[0][1] - candidates[1][1] < 5.0
        )
        needs_context = (
            ruleset is None
            or mode.mode_kind
            in {
                "container",
                "context",
                "ambiguous",
                "navigation_hub",
                "semantic_modifier",
            }
            or close_alternative
        )
        assumptions = []
        if needs_context:
            assumptions.append("La modalità precisa va confermata da UI, pannello Regole o osservazione live.")
        if ruleset and ruleset.lifecycle not in {"active", "current", "contextual", "parallel"}:
            assumptions.append(f"Ruleset con lifecycle {ruleset.lifecycle}; non trattarlo come regola corrente.")
        if constraints.get("forbidden_resources"):
            assumptions.append(
                "Vincolo di spesa riconosciuto: "
                + ", ".join(str(item) for item in constraints["forbidden_resources"])
                + "."
            )
        if constraints.get("avoid_persistent_loss"):
            assumptions.append("Vincolo riconosciuto: evitare azioni con perdita persistente possibile.")
        return GoalInterpretation(
            query=query,
            mode_id=mode.mode_id,
            ruleset_id=ruleset.ruleset_id if ruleset else "",
            objective_id=objective.objective_id if objective else "",
            confidence=round(max(0.0, min(1.0, top_score / 100.0)), 4),
            alternatives=alternatives,
            needs_context=needs_context,
            assumptions=tuple(assumptions),
            constraints=constraints,
        )

    def plan_goal(
        self,
        query: str,
        *,
        facts: Mapping[str, Any] | None = None,
        state: GameState | None = None,
        game_version: str = "",
    ) -> GameIntelligenceResult:
        if state is None:
            state = GameState(facts=dict(facts or {}), game_version=game_version)
        elif facts:
            state = GameState(
                facts={**state.facts, **facts},
                observations=state.observations,
                active_mode_id=state.active_mode_id,
                active_ruleset_id=state.active_ruleset_id,
                game_version=game_version or state.game_version,
            )
        interpretation = self.interpret_goal(query, state=state, game_version=game_version)
        plan = self.planner.plan(interpretation, state)
        ruleset = self.registry.get_ruleset(interpretation.ruleset_id)
        evidence_ids = ruleset.evidence_claim_ids if ruleset else ()
        return GameIntelligenceResult(
            interpretation=interpretation,
            plan=plan,
            registry_version=self.registry.registry_version,
            game_version=game_version or state.game_version or self.registry.game_version,
            evidence_claim_ids=evidence_ids,
        )


def _extract_constraints(query: str) -> dict[str, Any]:
    normalized = _normalize(query)
    constraints: dict[str, Any] = {}
    forbidden_resources: set[str] = set()
    no_spend = bool(re.search(r"\b(senza|non|no)\b.*\b(spendere|spesa|usa(?:re)?|consumare)\b", normalized))
    if no_spend and re.search(r"\b(valuta|currency|moneta|monete)\b", normalized):
        forbidden_resources.update({"event_currency", "premium_currency", "gems"})
    if no_spend and re.search(r"\b(gemme|gemma|gems?|diamanti?)\b", normalized):
        forbidden_resources.update({"premium_currency", "gems"})
    if no_spend and re.search(r"\b(risorse|resources?)\b", normalized):
        constraints["forbid_any_resource_cost"] = True
    if forbidden_resources:
        constraints["forbidden_resources"] = tuple(sorted(forbidden_resources))
    if re.search(r"\b(senza|nessuna?|zero)\b.*\b(perdite|perdita|caduti|morti|casualt(?:y|ies))\b", normalized):
        constraints["avoid_persistent_loss"] = True
    return constraints


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_like = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_like.lower()).strip()


__all__ = ["GameIntelligenceResult", "GameIntelligenceService"]
