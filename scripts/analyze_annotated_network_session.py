"""Analyze a metadata-only proxy session using its manual semantic markers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.annotated_network_analysis_service import analyze_annotated_network_session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze_annotated_network_session(
        args.session_dir,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "path": result["path"],
                "record_count": result["record_count"],
                "message_count": result["message_count"],
                "semantic_window_count": len(result["semantic_windows"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
