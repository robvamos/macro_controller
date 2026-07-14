"""Ports and adapters connecting semantic actions to existing DDassistant capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from doomsday.intelligence.models import (
    ActionBinding,
    ActionDefinition,
    GameState,
    Observation,
    RulesetDefinition,
    utc_now_iso,
)


class ActionBindingProvider(Protocol):
    def resolve(
        self,
        action: ActionDefinition,
        *,
        ruleset: RulesetDefinition,
        state: GameState,
    ) -> ActionBinding | None: ...


@dataclass(slots=True)
class NullActionBindingProvider:
    """Keeps planning independent from GUI/SQLite and exposes missing bindings."""

    def resolve(
        self,
        action: ActionDefinition,
        *,
        ruleset: RulesetDefinition,
        state: GameState,
    ) -> ActionBinding | None:
        return None


class UIGraphMacroBindingProvider:
    """Lazy adapter for the existing UI-node to macro link service.

    The import is deliberately deferred so the intelligence core remains usable on
    machines without the Windows vision dependencies.
    """

    def __init__(self, resolver: Callable[..., object] | None = None) -> None:
        self._resolver = resolver

    def resolve(
        self,
        action: ActionDefinition,
        *,
        ruleset: RulesetDefinition,
        state: GameState,
    ) -> ActionBinding | None:
        if not action.macro_intent or not action.target_ui_node:
            return None
        resolver = self._resolver or _load_ui_graph_resolver()
        plan = resolver(
            graph_id="doomsday-default-ui-graph",
            node_id=action.target_ui_node,
            intent_key=action.macro_intent,
        )
        candidates = tuple(getattr(plan, "candidate_links", ()) or ())
        if not candidates:
            return None
        candidate = sorted(
            candidates,
            key=lambda item: (
                0 if getattr(item, "relation_type", "") == "preferred" else 1,
                int(getattr(item, "priority", 100)),
            ),
        )[0]
        macro_id = getattr(candidate, "macro_id", None)
        macro_name = getattr(candidate, "macro_name", None)
        if macro_id is None and not macro_name:
            return None
        return ActionBinding(
            action_id=action.action_id,
            binding_type="macro",
            binding_id=str(macro_id or macro_name),
            label=str(macro_name or f"Macro {macro_id}"),
            confidence=1.0,
            metadata={
                "macro_id": macro_id,
                "relation_type": getattr(candidate, "relation_type", "candidate"),
                "priority": getattr(candidate, "priority", 100),
                "ruleset_id": ruleset.ruleset_id,
            },
        )


def observations_from_ui_evaluation(evaluation: object) -> tuple[Observation, ...]:
    """Translate a UI graph evaluation without importing its vision types."""

    observed_at = utc_now_iso()
    observations: list[Observation] = []
    graph_id = str(getattr(evaluation, "graph_id", "doomsday-default-ui-graph"))
    for result in tuple(getattr(evaluation, "node_results", ()) or ()):
        node_id = str(getattr(result, "node_id", ""))
        if not node_id:
            continue
        condition_results = tuple(getattr(result, "condition_results", ()) or ())
        # Structural nodes are not observations and must remain unknown to the
        # state estimator until they acquire visual recognition conditions.
        if not bool(getattr(result, "observable", bool(condition_results))):
            continue
        active = bool(getattr(result, "active", False))
        confidence = float(getattr(result, "confidence", 0.0))
        observations.append(
            Observation(
                key=f"ui.node.{node_id}.active",
                value=active,
                confidence=max(0.0, min(1.0, confidence)),
                source_id="ui-graph",
                observed_at=observed_at,
                evidence_id=f"{graph_id}:{node_id}:{observed_at}",
                metadata={"graph_id": graph_id, "node_id": node_id},
            )
        )
    if observations:
        observations.append(
            Observation(
                key="ui.observed",
                value=True,
                confidence=max(item.confidence for item in observations),
                source_id="ui-graph",
                observed_at=observed_at,
                metadata={"graph_id": graph_id},
            )
        )
    return tuple(observations)


def _load_ui_graph_resolver() -> Callable[..., object]:
    from services.ui_graph_macro_link_service import get_macro_plan_for_ui_node

    return get_macro_plan_for_ui_node


__all__ = [
    "ActionBindingProvider",
    "NullActionBindingProvider",
    "UIGraphMacroBindingProvider",
    "observations_from_ui_evaluation",
]
