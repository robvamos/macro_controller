"""OCR and classify the complete frames of one hero-learning session."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.hero_learning_analysis_service import analyze_hero_learning_session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir")
    parser.add_argument("--output-root")
    args = parser.parse_args()
    kwargs = {"output_root": args.output_root} if args.output_root else {}
    result = analyze_hero_learning_session(args.session_dir, **kwargs)
    counts = {}
    for item in result["payload"]["observations"]:
        node_id = item["screen"]["node_id"]
        counts[node_id] = counts.get(node_id, 0) + 1
    print(json.dumps({"path": result["path"], "screen_counts": counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
