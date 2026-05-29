"""Print macro suggestions inferred from learning-mode sessions."""

from __future__ import annotations

from pathlib import Path
import os
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    os.chdir(REPO_ROOT)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from services.learning_pattern_service import suggest_repeated_learning_patterns

    suggestions = suggest_repeated_learning_patterns(min_count=2, max_pattern_length=4)
    if not suggestions:
        print("Nessun pattern ripetuto sufficiente per proporre macro candidate.")
        return 0

    for index, suggestion in enumerate(suggestions, start=1):
        print(f"{index}. {suggestion.suggested_macro_name}")
        print(f"   elementi: {suggestion.element_ids}")
        print(f"   occorrenze: {suggestion.count}")
        print(f"   confidenza: {suggestion.confidence}")
        print(f"   macro sorgenti: {suggestion.source_macro_ids}")
        print(f"   note: {suggestion.notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
