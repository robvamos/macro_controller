"""Compare post-action perception with plan effects and objective criteria."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from doomsday.intelligence.models import GamePlan, GameState


@dataclass(frozen=True, slots=True)
class StepOutcome:
    action_id: str
    matched_effects: Mapping[str, Any]
    missing_effects: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class OutcomeAssessment:
    plan_id: str
    status: str
    objective_complete: bool
    matched_success_facts: Mapping[str, Any]
    missing_success_facts: Mapping[str, Any]
    step_outcomes: tuple[StepOutcome, ...]
    discrepancies: tuple[str, ...]


class OutcomeEvaluator:
    def evaluate(
        self,
        plan: GamePlan,
        *,
        post_state: GameState,
        executed_action_ids: Iterable[str],
    ) -> OutcomeAssessment:
        facts = post_state.materialize()
        executed = set(executed_action_ids)
        step_outcomes: list[StepOutcome] = []
        discrepancies: list[str] = []
        for step in plan.steps:
            if step.action_id not in executed:
                continue
            matched, missing = _partition_facts(facts, step.expected_effects)
            step_outcomes.append(StepOutcome(step.action_id, matched, missing))
            if missing:
                discrepancies.append(
                    f"{step.action_id}: effetti non osservati: "
                    + ", ".join(f"{key}={value!r}" for key, value in missing.items())
                )

        matched_success, missing_success = _partition_facts(facts, plan.success_facts)
        objective_complete = bool(plan.success_facts) and not missing_success
        if objective_complete:
            status = "completed"
        elif step_outcomes and any(item.missing_effects for item in step_outcomes):
            status = "effect_mismatch"
        else:
            status = "incomplete"
        return OutcomeAssessment(
            plan_id=plan.plan_id,
            status=status,
            objective_complete=objective_complete,
            matched_success_facts=matched_success,
            missing_success_facts=missing_success,
            step_outcomes=tuple(step_outcomes),
            discrepancies=tuple(discrepancies),
        )


def _partition_facts(
    facts: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    matched = {key: value for key, value in expected.items() if facts.get(key) == value}
    missing = {key: value for key, value in expected.items() if facts.get(key) != value}
    return matched, missing


__all__ = ["OutcomeAssessment", "OutcomeEvaluator", "StepOutcome"]
