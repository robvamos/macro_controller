"""Policy gate and executor port for guarded, one-step-at-a-time execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from doomsday.intelligence.models import (
    ActionBinding,
    AutomationPolicy,
    GameState,
    PlanStep,
    RiskClass,
    utc_now_iso,
)


@dataclass(frozen=True, slots=True)
class ExecutionPolicyContext:
    user_confirmed: bool = False
    session_allows_autonomy: bool = False
    perception_confidence: float = 0.0
    minimum_perception_confidence: float = 0.75
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionPolicyDecision:
    allowed: bool
    reason: str
    requires_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    action_id: str
    binding_id: str
    status: str
    started_at: str
    completed_at: str
    attempted_effects: Mapping[str, Any] = field(default_factory=dict)
    error: str = ""
    perception_requested: bool = True


class StepExecutor(Protocol):
    def execute(
        self,
        step: PlanStep,
        *,
        binding: ActionBinding,
        state: GameState,
        timeout_seconds: float,
    ) -> ExecutionReceipt: ...


class ExecutionPolicyGate:
    """Re-evaluate authority and fresh state immediately before one step."""

    NON_EXECUTABLE_STATUSES = {"blocked", "excluded", "manual", "suggested", "skipped", "unbound"}

    def evaluate(
        self,
        step: PlanStep,
        *,
        state: GameState,
        context: ExecutionPolicyContext,
    ) -> ExecutionPolicyDecision:
        if step.status in self.NON_EXECUTABLE_STATUSES:
            return ExecutionPolicyDecision(False, f"Stato non eseguibile: {step.status}.")
        if step.binding is None:
            return ExecutionPolicyDecision(False, "Manca un binding executor verificato.")
        if context.perception_confidence < context.minimum_perception_confidence:
            return ExecutionPolicyDecision(False, "Confidenza percettiva insufficiente o non aggiornata.")
        missing = _missing_facts(state.materialize(), step.preconditions)
        if missing:
            return ExecutionPolicyDecision(
                False,
                "Precondizioni non più valide: " + ", ".join(missing),
            )
        confirmation_required = (
            step.automation_policy == AutomationPolicy.CONFIRM_EACH
            or step.risk_class in {RiskClass.HIGH, RiskClass.CRITICAL}
        )
        if confirmation_required and not context.user_confirmed:
            return ExecutionPolicyDecision(
                False,
                "Conferma esplicita richiesta immediatamente prima dell'azione.",
                requires_confirmation=True,
            )
        if step.automation_policy != AutomationPolicy.AUTONOMOUS and not confirmation_required:
            return ExecutionPolicyDecision(False, "La policy dell'azione non consente esecuzione automatica.")
        if not confirmation_required and not context.session_allows_autonomy:
            return ExecutionPolicyDecision(False, "Autonomia non autorizzata per questa sessione.")
        return ExecutionPolicyDecision(True, "Policy, binding e precondizioni verificati.")


def failed_receipt(step: PlanStep, binding: ActionBinding, error: str) -> ExecutionReceipt:
    now = utc_now_iso()
    return ExecutionReceipt(
        action_id=step.action_id,
        binding_id=binding.binding_id,
        status="failed",
        started_at=now,
        completed_at=now,
        attempted_effects=step.expected_effects,
        error=error,
    )


def _missing_facts(facts: Mapping[str, Any], expected: Mapping[str, Any]) -> list[str]:
    return [f"{key}={value!r}" for key, value in expected.items() if facts.get(key) != value]


__all__ = [
    "ExecutionPolicyContext",
    "ExecutionPolicyDecision",
    "ExecutionPolicyGate",
    "ExecutionReceipt",
    "StepExecutor",
    "failed_receipt",
]
