"""Export shared Doomsday learning knowledge to tracked files."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.shared_knowledge_export_service import SHARED_KNOWLEDGE_DIR, export_shared_knowledge


def main() -> int:
    summary = export_shared_knowledge(SHARED_KNOWLEDGE_DIR)
    print(f"Shared knowledge exported to {summary['output_dir']}")
    print(f"Game elements: {summary['game_elements']}")
    print(f"Learning sessions: {summary['learning_sessions']}")
    print(f"UI graph nodes: {summary['ui_nodes']}")
    print(f"UI graph edges: {summary['ui_edges']}")
    print(f"Pattern suggestions: {summary['pattern_suggestions']}")
    print(f"Hero observations: {summary['hero_observations']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
