"""Declared hero-inspection workflow; visual bindings are learned separately."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from doomsday.vision.semantic_workflow import load_semantic_workflow


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HERO_INSPECTION_WORKFLOW = (
    PROJECT_ROOT / "data" / "doomsday" / "knowledge" / "hero_inspection_workflow.json"
)


def load_hero_inspection_workflow(
    path: str | Path = DEFAULT_HERO_INSPECTION_WORKFLOW,
) -> dict[str, Any]:
    return load_semantic_workflow(path)


__all__ = ["DEFAULT_HERO_INSPECTION_WORKFLOW", "load_hero_inspection_workflow"]
