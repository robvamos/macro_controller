"""Evidence-gated semantic workflows layered above raw UI detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VALID_MATURITY_STATES = {"expected", "observed_unlabeled", "labeled", "validated"}


def load_semantic_workflow(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_semantic_workflow(payload)
    return payload


def validate_semantic_workflow(payload: dict[str, Any]) -> None:
    if payload.get("schema") != "doomsday.semantic_workflow.v1":
        raise ValueError("Unsupported semantic workflow schema")
    nodes = payload.get("nodes") or []
    transitions = payload.get("transitions") or []
    node_ids = [node.get("node_id") for node in nodes]
    if not node_ids or any(not node_id for node_id in node_ids):
        raise ValueError("Semantic workflow requires named nodes")
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("Semantic workflow node IDs must be unique")
    known_nodes = set(node_ids)

    for node in nodes:
        _validate_maturity(node)
    transition_ids = set()
    for transition in transitions:
        transition_id = transition.get("transition_id")
        if not transition_id or transition_id in transition_ids:
            raise ValueError("Semantic workflow transition IDs must be unique and non-empty")
        transition_ids.add(transition_id)
        if transition.get("from_node_id") not in known_nodes or transition.get("to_node_id") not in known_nodes:
            raise ValueError(f"Unknown node referenced by transition {transition_id}")
        _validate_maturity(transition)
        if transition.get("automation_allowed") and transition.get("maturity") != "validated":
            raise ValueError(f"Automation cannot be enabled before validation: {transition_id}")


def can_automate_transition(workflow: dict[str, Any], transition_id: str) -> bool:
    """Require explicit validation plus good before/after frames for automation."""
    validate_semantic_workflow(workflow)
    transition = next(
        (item for item in workflow.get("transitions", []) if item.get("transition_id") == transition_id),
        None,
    )
    if transition is None:
        raise KeyError(transition_id)
    if transition.get("maturity") != "validated" or not transition.get("automation_allowed"):
        return False
    evidence = transition.get("evidence") or []
    valid_kinds = {
        item.get("kind")
        for item in evidence
        if item.get("quality", {}).get("valid") is True and item.get("human_confirmed") is True
    }
    return {"before_frame", "after_frame"}.issubset(valid_kinds)


def _validate_maturity(item: dict[str, Any]) -> None:
    maturity = item.get("maturity")
    if maturity not in VALID_MATURITY_STATES:
        raise ValueError(f"Unsupported maturity state: {maturity}")


__all__ = [
    "VALID_MATURITY_STATES",
    "can_automate_transition",
    "load_semantic_workflow",
    "validate_semantic_workflow",
]
