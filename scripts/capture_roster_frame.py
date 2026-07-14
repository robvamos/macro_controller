"""Cattura un frame read-only della finestra Doomsday già visibile."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from doomsday.services.live_roster_service import LiveRosterAcquisitionService, NativeWindowCaptureProvider


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".tools") / "roster-captures" / f"doomsday-{datetime.now():%Y%m%d-%H%M%S}.png",
        help="Destinazione PNG (default sotto .tools, esclusa da Git).",
    )
    arguments = parser.parse_args()
    path = LiveRosterAcquisitionService().capture_supervised_frame(
        NativeWindowCaptureProvider(),
        destination=arguments.output,
    )
    print(path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
