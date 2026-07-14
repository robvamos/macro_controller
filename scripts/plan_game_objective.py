"""Inspect how the intelligence core understands and plans a game objective."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.paths import DOOMSDAY_DOMAIN_REGISTRY_PATH  # noqa: E402
from doomsday.intelligence.registry import DomainRegistry  # noqa: E402
from services.game_intelligence_service import plan_game_goal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("goal", nargs="?", help="Obiettivo in linguaggio naturale")
    parser.add_argument("--game-version", default="", help="Versione del gioco, es. 1.56.0")
    parser.add_argument(
        "--fact",
        action="append",
        default=[],
        metavar="KEY=JSON",
        help="Fatto già osservato; ripetibile, es. runtime.ready=true",
    )
    parser.add_argument("--list-modes", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    registry = DomainRegistry.load(DOOMSDAY_DOMAIN_REGISTRY_PATH)
    if args.validate:
        issues = registry.validate()
        print(json.dumps({"valid": not issues, "issues": issues}, ensure_ascii=False, indent=2))
        return 1 if issues else 0
    if args.list_modes:
        print(
            json.dumps(
                [
                    {
                        "mode_id": mode.mode_id,
                        "label": mode.label,
                        "lifecycle": mode.lifecycle,
                        "rulesets": [item.ruleset_id for item in mode.rulesets],
                    }
                    for mode in registry.modes
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not args.goal:
        parser.error("specifica un goal oppure usa --list-modes/--validate")

    result = plan_game_goal(
        args.goal,
        facts=_parse_facts(args.fact),
        game_version=args.game_version,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _parse_facts(raw_facts: list[str]) -> dict[str, object]:
    facts: dict[str, object] = {}
    for raw in raw_facts:
        if "=" not in raw:
            raise ValueError(f"fact non valido: {raw!r}")
        key, raw_value = raw.split("=", 1)
        facts[key.strip()] = json.loads(raw_value)
    return facts


if __name__ == "__main__":
    raise SystemExit(main())
