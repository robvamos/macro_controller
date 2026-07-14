"""Stampa l'inventario read-only dei runtime Doomsday locali."""

from __future__ import annotations

import argparse
import json

from doomsday.runtime.discovery import DEFAULT_RUNTIME_REGISTRY_PATH, GameRuntimeDiscoveryService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help=f"Aggiorna anche {DEFAULT_RUNTIME_REGISTRY_PATH}",
    )
    arguments = parser.parse_args()
    service = GameRuntimeDiscoveryService()
    if arguments.write:
        path = service.write_snapshot()
        print(path)
        return 0
    print(json.dumps(service.discover(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
