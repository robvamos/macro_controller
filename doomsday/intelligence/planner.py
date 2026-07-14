"""Conservative workflow planner with explicit safety and binding visibility."""

from __future__ import annotations

from uuid import uuid4

from doomsday.intelligence.adapters import ActionBindingProvider, NullActionBindingProvider
from doomsday.intelligence.models import (
    AutomationPolicy,
    GamePlan,
    GameState,
    GoalInterpretation,
    PlanStep,
    RiskClass,
    RulesetDefinition,
    utc_now_iso,
)
from doomsday.intelligence.registry import DomainRegistry


class WorkflowPlanner:
    """Build an explainable semantic plan, never raw input coordinates."""

    def __init__(
        self,
        registry: DomainRegistry,
        *,
        binding_provider: ActionBindingProvider | None = None,
    ) -> None:
        self.registry = registry
        self.binding_provider = binding_provider or NullActionBindingProvider()

    def plan(
        self,
        interpretation: GoalInterpretation,
        state: GameState,
    ) -> GamePlan:
        ruleset = self.registry.get_ruleset(interpretation.ruleset_id)
        if ruleset is None:
            return _blocked_plan(
                interpretation,
                state,
                reason=f"Ruleset non disponibile: {interpretation.ruleset_id or '<non riconosciuto>'}",
            )

        objective = next(
            (item for item in ruleset.objectives if item.objective_id == interpretation.objective_id),
            ruleset.objectives[0] if ruleset.objectives else None,
        )
        success_facts = dict(objective.goal_facts if objective else ruleset.success_facts)
        if not success_facts:
            success_facts = dict(ruleset.success_facts)

        initial_facts = state.materialize()
        projected_facts = dict(initial_facts)
        steps: list[PlanStep] = []
        blocking_reasons: list[str] = []
        warnings: list[str] = []
        if interpretation.needs_context:
            blocking_reasons.append(
                "Il contesto di gioco è ambiguo: confermare modalità e ruleset da UI o pannello Regole."
            )

        for action_id in ruleset.workflow:
            action = self.registry.get_action(action_id)
            if action is None:
                blocking_reasons.append(f"Azione sconosciuta nel workflow: {action_id}")
                continue

            if _facts_match(projected_facts, action.effects):
                steps.append(
                    PlanStep(
                        index=len(steps) + 1,
                        action_id=action.action_id,
                        label=action.label,
                        status="skipped",
                        reason="Effetti già osservati nello stato corrente o previsto.",
                        risk_class=action.risk_class,
                        automation_policy=action.automation_policy,
                        preconditions=action.preconditions,
                        expected_effects=action.effects,
                        macro_intent=action.macro_intent,
                        target_ui_node=action.target_ui_node,
                    )
                )
                continue

            constraint_violations = _constraint_violations(action.cost_details, interpretation.constraints)
            if constraint_violations:
                steps.append(
                    PlanStep(
                        index=len(steps) + 1,
                        action_id=action.action_id,
                        label=action.label,
                        status="excluded",
                        reason="Esclusa dai vincoli dell'obiettivo: " + "; ".join(constraint_violations),
                        risk_class=action.risk_class,
                        automation_policy=action.automation_policy,
                        preconditions=action.preconditions,
                        expected_effects=action.effects,
                        macro_intent=action.macro_intent,
                        target_ui_node=action.target_ui_node,
                    )
                )
                continue

            missing = _missing_facts(projected_facts, action.preconditions)
            if missing:
                reason = f"Precondizioni mancanti per {action.action_id}: {', '.join(missing)}"
                blocking_reasons.append(reason)
                steps.append(
                    PlanStep(
                        index=len(steps) + 1,
                        action_id=action.action_id,
                        label=action.label,
                        status="blocked",
                        reason=reason,
                        risk_class=action.risk_class,
                        automation_policy=action.automation_policy,
                        preconditions=action.preconditions,
                        expected_effects=action.effects,
                        macro_intent=action.macro_intent,
                        target_ui_node=action.target_ui_node,
                    )
                )
                continue

            binding = self.binding_provider.resolve(action, ruleset=ruleset, state=state)
            status, reason = _execution_status(
                action.automation_policy,
                action.risk_class,
                has_binding=binding is not None,
                needs_binding=bool(action.macro_intent),
                initial_preconditions_met=_facts_match(initial_facts, action.preconditions),
            )
            if action.macro_intent and binding is None:
                warnings.append(
                    f"{action.action_id}: nessuna macro collegata all'intento {action.macro_intent}; il passo resta semantico."
                )
            if action.risk_class in {RiskClass.HIGH, RiskClass.CRITICAL}:
                warnings.append(f"{action.action_id}: azione ad alto rischio, non eseguire senza conferma.")
            steps.append(
                PlanStep(
                    index=len(steps) + 1,
                    action_id=action.action_id,
                    label=action.label,
                    status=status,
                    reason=reason,
                    risk_class=action.risk_class,
                    automation_policy=action.automation_policy,
                    preconditions=action.preconditions,
                    expected_effects=action.effects,
                    macro_intent=action.macro_intent,
                    target_ui_node=action.target_ui_node,
                    binding=binding,
                )
            )
            # Un piano non è una receipt: gli effetti diventano fatti solo dopo
            # esecuzione confermata e nuova osservazione del contesto di gioco.

        unmet_success = _missing_facts(projected_facts, success_facts)
        if unmet_success:
            warnings.append(
                "I criteri di successo richiedono verifica dall'esito, non sono fatti garantiti dal piano: "
                + ", ".join(unmet_success)
            )

        return GamePlan(
            plan_id=str(uuid4()),
            query=interpretation.query,
            mode_id=interpretation.mode_id,
            ruleset_id=interpretation.ruleset_id,
            objective_id=interpretation.objective_id,
            created_at=utc_now_iso(),
            steps=tuple(steps),
            initial_facts=initial_facts,
            projected_facts=projected_facts,
            success_facts=success_facts,
            blocked=bool(blocking_reasons),
            blocking_reasons=tuple(dict.fromkeys(blocking_reasons)),
            warnings=tuple(dict.fromkeys(warnings)),
        )


def _execution_status(
    policy: AutomationPolicy,
    risk: RiskClass,
    *,
    has_binding: bool,
    needs_binding: bool,
    initial_preconditions_met: bool,
) -> tuple[str, str]:
    if policy == AutomationPolicy.MANUAL:
        return "manual", "Il passo richiede osservazione o interazione umana."
    if policy == AutomationPolicy.SUGGEST_ONLY:
        return "suggested", "Il sistema può consigliare il passo ma non eseguirlo."
    if risk in {RiskClass.HIGH, RiskClass.CRITICAL} or policy == AutomationPolicy.CONFIRM_EACH:
        if needs_binding and not has_binding:
            return "unbound", "Conferma necessaria e nessun executor/macro ancora collegato."
        return "confirmation_required", "Serve conferma esplicita immediatamente prima dell'esecuzione."
    if needs_binding and not has_binding:
        return "unbound", "Nessun executor/macro collegato all'azione semantica."
    if initial_preconditions_met:
        return "ready", "Precondizioni osservate; il passo è pronto."
    return "planned", "Le precondizioni sono prodotte dai passi precedenti e andranno riverificate."


def _facts_match(facts: dict[str, object], expected: object) -> bool:
    if not isinstance(expected, dict):
        return True
    return all(key in facts and facts[key] == value for key, value in expected.items())


def _missing_facts(facts: dict[str, object], expected: object) -> list[str]:
    if not isinstance(expected, dict):
        return []
    return [f"{key}={value!r}" for key, value in expected.items() if facts.get(key) != value]


def _constraint_violations(
    cost_details: object,
    constraints: object,
) -> list[str]:
    if not isinstance(cost_details, dict) or not isinstance(constraints, dict):
        return []
    resources = tuple(str(item).lower() for item in cost_details.get("resources", ()) if item)
    violations: list[str] = []
    if constraints.get("forbid_any_resource_cost") and resources:
        violations.append("costo in risorse non consentito: " + ", ".join(resources))
    forbidden = tuple(str(item).lower() for item in constraints.get("forbidden_resources", ()) if item)
    matched = sorted(
        resource
        for resource in resources
        if any(token == resource or token in resource for token in forbidden)
    )
    if matched:
        violations.append("risorsa vietata: " + ", ".join(matched))
    persistent_loss = cost_details.get("persistent_loss_possible", False)
    if constraints.get("avoid_persistent_loss") and persistent_loss not in {False, None, "false", "no"}:
        violations.append("possibile perdita persistente")
    return violations


def _blocked_plan(
    interpretation: GoalInterpretation,
    state: GameState,
    *,
    reason: str,
) -> GamePlan:
    facts = state.materialize()
    return GamePlan(
        plan_id=str(uuid4()),
        query=interpretation.query,
        mode_id=interpretation.mode_id,
        ruleset_id=interpretation.ruleset_id,
        objective_id=interpretation.objective_id,
        created_at=utc_now_iso(),
        steps=(),
        initial_facts=facts,
        projected_facts=facts,
        success_facts={},
        blocked=True,
        blocking_reasons=(reason,),
    )


__all__ = ["WorkflowPlanner"]
